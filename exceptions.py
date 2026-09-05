"""Исключения модуля работы с exchangerate.host."""


class CurrencyApiError(Exception):
    """Базовая ошибка при обращении к API курсов валют."""


class RateNotAvailableError(CurrencyApiError):
    """Курс для запрошенной валютной пары не пришёл в ответе API."""
