"""Сопоставление названий стран с кодами валют (ISO 4217)."""
import re

COUNTRY_CURRENCY = {
    "россия": "RUB",
    "китай": "CNY",
    "сша": "USD",
    "америка": "USD",
    "германия": "EUR",
    "франция": "EUR",
    "италия": "EUR",
    "испания": "EUR",
    "греция": "EUR",
    "черногория": "EUR",
    "великобритания": "GBP",
    "англия": "GBP",
    "турция": "TRY",
    "оаэ": "AED",
    "дубай": "AED",
    "таиланд": "THB",
    "вьетнам": "VND",
    "грузия": "GEL",
    "армения": "AMD",
    "казахстан": "KZT",
    "узбекистан": "UZS",
    "киргизия": "KGS",
    "индия": "INR",
    "япония": "JPY",
    "южная корея": "KRW",
    "корея": "KRW",
    "египет": "EGP",
    "индонезия": "IDR",
    "бали": "IDR",
    "сербия": "RSD",
    "мальдивы": "MVR",
    "шри-ланка": "LKR",
    "бразилия": "BRL",
    "мексика": "MXN",
}

CURRENCY_CODE_PATTERN = re.compile(r"^[A-Za-z]{3}$")


def resolve_currency(text: str) -> str | None:
    """
    Возвращает код валюты по названию страны (из словаря) или, если строка
    похожа на код валюты (3 латинские буквы, например "USD"), возвращает её
    в верхнем регистре напрямую — чтобы не быть ограниченными конечным списком стран.
    """
    text = text.strip()
    by_country = COUNTRY_CURRENCY.get(text.lower())
    if by_country:
        return by_country

    if CURRENCY_CODE_PATTERN.match(text):
        return text.upper()

    return None
