"""Консольный тест модуля current_api — проверка перед сборкой бота."""
import sys

import config
from current_api import convert_currency, get_rate
from exceptions import CurrencyApiError

if __name__ == "__main__":
    if not config.CURRENCY_API_KEY:
        print("Не задан CURRENCY_API_KEY в .env")
        sys.exit(1)

    try:
        rate = get_rate(config.CURRENCY_API_KEY, "RUB", "CNY")
        print(f"Курс RUB -> CNY: {rate}")

        result = convert_currency(config.CURRENCY_API_KEY, 1000, "RUB", "CNY")
        print(f"1000 RUB = {result} CNY")
    except CurrencyApiError as e:
        print(f"Ошибка: {e}")
