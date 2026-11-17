"""Validações e tipos compartilhados da API FasTruck."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


BRASILIA = timezone(timedelta(hours=-3), name="America/Sao_Paulo")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def today_brasilia() -> date:
    return datetime.now(BRASILIA).date()


def validate_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ApiError(400, "Envie os dados como um objeto JSON.")
    return payload


def text(payload: dict, key: str, label: str, max_length: int,
         required: bool = False, min_length: int = 1) -> str:
    value = payload.get(key, "")
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ApiError(400, f"O campo {label} deve conter texto.")
    value = value.strip()
    if required and len(value) < min_length:
        raise ApiError(400, f"Preencha {label} com pelo menos {min_length} caractere(s).")
    if len(value) > max_length:
        raise ApiError(400, f"O campo {label} aceita no máximo {max_length} caracteres.")
    return value


def money_to_cents(value: object, legacy: bool = False) -> int:
    if isinstance(value, bool) or value is None:
        raise ApiError(400, "Informe um valor monetário válido.")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999999.99"):
            raise InvalidOperation
        rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if not legacy and (amount != rounded or amount.as_tuple().exponent < -2):
            raise ApiError(400, "Informe o valor com no máximo duas casas decimais.")
        return int(rounded * 100)
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        raise ApiError(400, "Informe um valor monetário válido, positivo ou zero.") from None
