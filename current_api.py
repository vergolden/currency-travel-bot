"""
Клиент для получения курсов валют и конвертации через API exchangerate.host.

Документация: https://exchangerate.host/documentation
Эндпоинты: /live (текущие курсы), /convert (конвертация суммы).
"""
import requests

from exceptions import CurrencyApiError, RateNotAvailableError

BASE_URL = "https://api.exchangerate.host"


def _check_success(data: dict, context: str) -> None:
    if not data.get("success", False):
        error = data.get("error", {})
        raise CurrencyApiError(
            f"{context}: {error.get('info') or error.get('type') or 'неизвестная ошибка API'}"
        )


def get_current_rate(api_key: str, default: str = "USD", currencies: list[str] | None = None) -> dict:
    """
    Возвращает сырой ответ /live: {"source": ..., "quotes": {"USDEUR": 0.85, ...}}.
    """
    currencies = currencies or ["EUR", "GBP", "JPY"]
    response = requests.get(
        f"{BASE_URL}/live",
        params={
            "access_key": api_key,
            "source": default,
            "currencies": ",".join(currencies),
        },
        timeout=10,
    )
    data = response.json()
    _check_success(data, "Не удалось получить курсы валют")
    return data


def get_rate(api_key: str, from_currency: str, to_currency: str) -> float:
    """Возвращает курс: сколько to_currency за 1 from_currency."""
    data = get_current_rate(api_key, default=from_currency, currencies=[to_currency])
    quote_key = f"{from_currency}{to_currency}"
    rate = data.get("quotes", {}).get(quote_key)
    if rate is None:
        raise RateNotAvailableError(
            f"Курс {from_currency} → {to_currency} недоступен через API"
        )
    return rate


def convert_currency(api_key: str, amount: float, from_currency: str, to_currency: str) -> float:
    """Конвертирует amount из from_currency в to_currency, возвращает результат."""
    response = requests.get(
        f"{BASE_URL}/convert",
        params={
            "access_key": api_key,
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
        },
        timeout=10,
    )
    data = response.json()
    _check_success(data, "Не удалось выполнить конвертацию")
    return data["result"]
