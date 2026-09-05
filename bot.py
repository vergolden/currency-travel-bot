"""
Telegram-бот «Кошелёк путешественника» — учёт расходов в поездках с конвертацией
через API exchangerate.host. Диалог хранит состояние в памяти процесса (sessions),
данные путешествий и расходов — в SQLite (database.py).
"""
import telebot
from telebot import types

import config
import database
from countries import resolve_currency
from current_api import get_rate
from exceptions import CurrencyApiError

bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

STEP_IDLE = "idle"
STEP_NEWTRIP_HOME = "newtrip_home"
STEP_NEWTRIP_DEST = "newtrip_dest"
STEP_NEWTRIP_CONFIRM_RATE = "newtrip_confirm_rate"
STEP_NEWTRIP_MANUAL_RATE = "newtrip_manual_rate"
STEP_NEWTRIP_AMOUNT = "newtrip_amount"
STEP_EXPENSE_CONFIRM = "expense_confirm"
STEP_SETRATE = "setrate"

# user_id -> {"step": ..., "data": {...}} — состояние диалога в памяти процесса.
sessions: dict[int, dict] = {}

WELCOME_TEXT = (
    "Привет! Я — «Кошелёк путешественника» 🧳\n\n"
    "Помогаю управлять финансами в поездках:\n"
    "• создаю кошельки для разных стран\n"
    "• конвертирую валюты по актуальному курсу\n"
    "• отслеживаю расходы и показываю остаток в двух валютах\n\n"
    "Начните с «Создать новое путешествие»."
)


def get_session(user_id: int) -> dict:
    return sessions.setdefault(user_id, {"step": STEP_IDLE, "data": {}})


def main_menu_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("✈️ Создать новое путешествие", callback_data="menu_newtrip"),
        types.InlineKeyboardButton("🧳 Мои путешествия", callback_data="menu_trips"),
        types.InlineKeyboardButton("💰 Баланс", callback_data="menu_balance"),
        types.InlineKeyboardButton("📜 История расходов", callback_data="menu_history"),
        types.InlineKeyboardButton("🔄 Изменить курс", callback_data="menu_setrate"),
    )
    return kb


def yes_no_keyboard(yes_data: str, no_data: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✅ Да", callback_data=yes_data),
        types.InlineKeyboardButton("❌ Нет", callback_data=no_data),
    )
    return kb


def start_newtrip(chat_id: int, user_id: int) -> None:
    session = get_session(user_id)
    session["step"] = STEP_NEWTRIP_HOME
    session["data"] = {}
    bot.send_message(chat_id, "Из какой страны вы уезжаете? (например, Россия)")


def start_setrate(chat_id: int, user_id: int) -> None:
    trip = database.get_active_trip(user_id)
    if not trip:
        bot.send_message(chat_id, "Сначала создайте путешествие — /newtrip")
        return
    session = get_session(user_id)
    session["step"] = STEP_SETRATE
    bot.send_message(
        chat_id,
        f"Текущий курс: 1 {trip['home_currency']} = {trip['rate']} {trip['dest_currency']}\n"
        "Введите новый курс числом.",
    )


def show_trips(chat_id: int, user_id: int) -> None:
    trips = database.get_trips(user_id)
    if not trips:
        bot.send_message(chat_id, "У вас пока нет путешествий. Создайте первое — /newtrip")
        return
    kb = types.InlineKeyboardMarkup(row_width=1)
    for trip in trips:
        marker = "▶️ " if trip["is_active"] else ""
        label = f"{marker}{trip['home_country']} → {trip['dest_country']}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"switch_{trip['id']}"))
    bot.send_message(chat_id, "Ваши путешествия (нажмите, чтобы переключиться):", reply_markup=kb)


def show_balance(chat_id: int, user_id: int) -> None:
    trip = database.get_active_trip(user_id)
    if not trip:
        bot.send_message(chat_id, "Нет активного путешествия. Создайте — /newtrip")
        return
    bot.send_message(
        chat_id,
        f"{trip['home_country']} → {trip['dest_country']}\n"
        f"Остаток: {round(trip['balance_dest'], 2)} {trip['dest_currency']} "
        f"= {round(trip['balance_home'], 2)} {trip['home_currency']}",
    )


def show_history(chat_id: int, user_id: int) -> None:
    trip = database.get_active_trip(user_id)
    if not trip:
        bot.send_message(chat_id, "Нет активного путешествия. Создайте — /newtrip")
        return
    history = database.get_history(trip["id"])
    if not history:
        bot.send_message(chat_id, "Расходов пока нет.")
        return
    lines = ["История расходов (последние операции):"]
    for expense in history:
        lines.append(
            f"{expense['created_at']} — {expense['amount_dest']} {trip['dest_currency']} "
            f"= {round(expense['amount_home'], 2)} {trip['home_currency']}"
        )
    bot.send_message(chat_id, "\n".join(lines))


def confirm_api_rate(chat_id: int, user_id: int) -> None:
    session = get_session(user_id)
    data = session["data"]
    data["rate"] = data["api_rate"]
    session["step"] = STEP_NEWTRIP_AMOUNT
    bot.send_message(chat_id, f"Введите начальную сумму в {data['home_currency']}.")


def confirm_expense(chat_id: int, user_id: int) -> None:
    session = get_session(user_id)
    pending = session["data"].get("pending_expense")
    if not pending:
        bot.send_message(chat_id, "Нет расхода, ожидающего подтверждения.")
        return
    database.add_expense(pending["trip_id"], pending["amount_dest"], pending["amount_home"])
    trip = database.get_trip(pending["trip_id"])
    session["step"] = STEP_IDLE
    session["data"] = {}
    bot.send_message(
        chat_id,
        f"Записано ✅\nОстаток: {round(trip['balance_dest'], 2)} {trip['dest_currency']} "
        f"= {round(trip['balance_home'], 2)} {trip['home_currency']}",
    )


@bot.message_handler(commands=["start"])
def handle_start(message: types.Message) -> None:
    sessions[message.from_user.id] = {"step": STEP_IDLE, "data": {}}
    bot.send_message(message.chat.id, WELCOME_TEXT, reply_markup=main_menu_keyboard())


@bot.message_handler(commands=["newtrip"])
def handle_newtrip(message: types.Message) -> None:
    start_newtrip(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["switch"])
def handle_switch(message: types.Message) -> None:
    show_trips(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["balance"])
def handle_balance(message: types.Message) -> None:
    show_balance(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["history"])
def handle_history(message: types.Message) -> None:
    show_history(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["setrate"])
def handle_setrate(message: types.Message) -> None:
    start_setrate(message.chat.id, message.from_user.id)


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: types.CallbackQuery) -> None:
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data

    if action == "menu_newtrip":
        start_newtrip(chat_id, user_id)
    elif action == "menu_trips":
        show_trips(chat_id, user_id)
    elif action == "menu_balance":
        show_balance(chat_id, user_id)
    elif action == "menu_history":
        show_history(chat_id, user_id)
    elif action == "menu_setrate":
        start_setrate(chat_id, user_id)
    elif action.startswith("switch_"):
        trip_id = int(action.split("_", 1)[1])
        database.set_active_trip(user_id, trip_id)
        bot.send_message(chat_id, "Путешествие переключено.")
        show_balance(chat_id, user_id)
    elif action == "rate_yes":
        confirm_api_rate(chat_id, user_id)
    elif action == "rate_no":
        session = get_session(user_id)
        session["step"] = STEP_NEWTRIP_MANUAL_RATE
        bot.send_message(
            chat_id,
            "Введите курс вручную — сколько единиц валюты назначения за 1 единицу домашней валюты.",
        )
    elif action == "expense_yes":
        confirm_expense(chat_id, user_id)
    elif action == "expense_no":
        session = get_session(user_id)
        session["step"] = STEP_IDLE
        session["data"] = {}
        bot.send_message(chat_id, "Хорошо, не учитываю как расход.")

    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["text"])
def handle_text(message: types.Message) -> None:
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    session = get_session(user_id)
    step = session["step"]
    data = session["data"]

    if step == STEP_NEWTRIP_HOME:
        currency = resolve_currency(text)
        if not currency:
            bot.send_message(chat_id, "Не узнал такую страну. Напишите название страны или код валюты (например, USD).")
            return
        data["home_country"] = text
        data["home_currency"] = currency
        session["step"] = STEP_NEWTRIP_DEST
        bot.send_message(chat_id, "В какую страну едете?")
        return

    if step == STEP_NEWTRIP_DEST:
        currency = resolve_currency(text)
        if not currency:
            bot.send_message(chat_id, "Не узнал такую страну. Напишите название страны или код валюты.")
            return
        data["dest_country"] = text
        data["dest_currency"] = currency
        try:
            rate = get_rate(config.CURRENCY_API_KEY, data["home_currency"], data["dest_currency"])
        except CurrencyApiError as e:
            bot.send_message(chat_id, f"Не удалось получить курс через API: {e}\nВведите курс вручную числом.")
            session["step"] = STEP_NEWTRIP_MANUAL_RATE
            return
        data["api_rate"] = rate
        session["step"] = STEP_NEWTRIP_CONFIRM_RATE
        bot.send_message(
            chat_id,
            f"Курс: 1 {data['home_currency']} = {rate} {data['dest_currency']}\nКурс подходит?",
            reply_markup=yes_no_keyboard("rate_yes", "rate_no"),
        )
        return

    if step == STEP_NEWTRIP_CONFIRM_RATE:
        bot.send_message(chat_id, "Пожалуйста, нажмите «Да» или «Нет» выше.")
        return

    if step == STEP_NEWTRIP_MANUAL_RATE:
        try:
            rate = float(text.replace(",", "."))
        except ValueError:
            bot.send_message(chat_id, "Нужно число, например 12.5. Попробуйте ещё раз.")
            return
        data["rate"] = rate
        session["step"] = STEP_NEWTRIP_AMOUNT
        bot.send_message(chat_id, f"Введите начальную сумму в {data['home_currency']}.")
        return

    if step == STEP_NEWTRIP_AMOUNT:
        try:
            amount = float(text.replace(",", "."))
        except ValueError:
            bot.send_message(chat_id, "Нужно число. Попробуйте ещё раз.")
            return
        rate = data.get("rate") or data.get("api_rate")
        balance_dest = amount * rate
        database.create_trip(
            user_id=user_id,
            home_country=data["home_country"],
            home_currency=data["home_currency"],
            dest_country=data["dest_country"],
            dest_currency=data["dest_currency"],
            rate=rate,
            balance_home=amount,
            balance_dest=balance_dest,
        )
        home_country, dest_country = data["home_country"], data["dest_country"]
        home_currency, dest_currency = data["home_currency"], data["dest_currency"]
        session["step"] = STEP_IDLE
        session["data"] = {}
        bot.send_message(
            chat_id,
            f"Путешествие создано! 🎉\n{home_country} → {dest_country}\n"
            f"Курс: 1 {home_currency} = {rate} {dest_currency}\n"
            f"Баланс: {amount} {home_currency} = {round(balance_dest, 2)} {dest_currency}",
            reply_markup=main_menu_keyboard(),
        )
        return

    if step == STEP_SETRATE:
        try:
            rate = float(text.replace(",", "."))
        except ValueError:
            bot.send_message(chat_id, "Нужно число. Попробуйте ещё раз.")
            return
        trip = database.get_active_trip(user_id)
        if not trip:
            bot.send_message(chat_id, "Нет активного путешествия.")
            session["step"] = STEP_IDLE
            return
        database.update_rate(trip["id"], rate)
        session["step"] = STEP_IDLE
        bot.send_message(chat_id, f"Курс обновлён: 1 {trip['home_currency']} = {rate} {trip['dest_currency']}")
        return

    if step == STEP_EXPENSE_CONFIRM:
        bot.send_message(chat_id, "Пожалуйста, нажмите «Да» или «Нет» выше.")
        return

    # Свободный ввод вне сценария: число — расход в валюте активного путешествия
    try:
        amount_dest = float(text.replace(",", "."))
    except ValueError:
        bot.send_message(chat_id, "Не понял сообщение. Выберите действие в меню.", reply_markup=main_menu_keyboard())
        return

    trip = database.get_active_trip(user_id)
    if not trip:
        bot.send_message(chat_id, "Сначала создайте путешествие — /newtrip")
        return

    amount_home = amount_dest / trip["rate"]
    data["pending_expense"] = {
        "trip_id": trip["id"],
        "amount_dest": amount_dest,
        "amount_home": amount_home,
    }
    session["step"] = STEP_EXPENSE_CONFIRM
    bot.send_message(
        chat_id,
        f"{amount_dest} {trip['dest_currency']} = {round(amount_home, 2)} {trip['home_currency']}\n"
        "Учесть как расход?",
        reply_markup=yes_no_keyboard("expense_yes", "expense_no"),
    )


if __name__ == "__main__":
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN в .env")
    if not config.CURRENCY_API_KEY:
        raise SystemExit("Не задан CURRENCY_API_KEY в .env")
    database.init_db()
    print("Бот запущен")
    bot.infinity_polling()
