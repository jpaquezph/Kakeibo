"""Valor monetario con precision exacta. Nunca usar float para dinero."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class Moneda(str, Enum):
    ARS = "ARS"
    USD = "USD"


_SYMBOLS = {Moneda.ARS: "$", Moneda.USD: "$us"}

_CENTS = Decimal("100")
_TWO_DECIMALS = Decimal("0.01")


class CurrencyMismatchError(ValueError):
    """Se intento operar entre montos de distinta moneda."""


class Money:
    """Monto monetario representado internamente como centavos (int).

    Nunca opera con float. Las conversiones desde/hacia Decimal son explicitas
    y redondean a 2 decimales con ROUND_HALF_UP.
    """

    __slots__ = ("_cents", "moneda")

    def __init__(self, cents: int, moneda: Moneda | str):
        self._cents = int(cents)
        self.moneda = Moneda(moneda)

    @classmethod
    def from_decimal(cls, amount: Decimal | str | int, moneda: Moneda | str) -> "Money":
        d = Decimal(str(amount)).quantize(_TWO_DECIMALS, rounding=ROUND_HALF_UP)
        return cls(int(d * _CENTS), moneda)

    @classmethod
    def zero(cls, moneda: Moneda | str) -> "Money":
        return cls(0, moneda)

    @property
    def cents(self) -> int:
        return self._cents

    @property
    def amount(self) -> Decimal:
        return (Decimal(self._cents) / _CENTS).quantize(_TWO_DECIMALS)

    def _check_same_currency(self, other: "Money") -> None:
        if self.moneda != other.moneda:
            raise CurrencyMismatchError(
                f"No se pueden combinar montos de distinta moneda: {self.moneda.value} vs {other.moneda.value}"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self._cents + other._cents, self.moneda)

    def __sub__(self, other: "Money") -> "Money":
        self._check_same_currency(other)
        return Money(self._cents - other._cents, self.moneda)

    def __neg__(self) -> "Money":
        return Money(-self._cents, self.moneda)

    def __mul__(self, factor: int) -> "Money":
        if not isinstance(factor, int):
            raise TypeError("Money solo se puede multiplicar por un entero (ej: cantidad de cuotas)")
        return Money(self._cents * factor, self.moneda)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Money) and self._cents == other._cents and self.moneda == other.moneda

    def __lt__(self, other: "Money") -> bool:
        self._check_same_currency(other)
        return self._cents < other._cents

    def __le__(self, other: "Money") -> bool:
        self._check_same_currency(other)
        return self._cents <= other._cents

    def __gt__(self, other: "Money") -> bool:
        self._check_same_currency(other)
        return self._cents > other._cents

    def __ge__(self, other: "Money") -> bool:
        self._check_same_currency(other)
        return self._cents >= other._cents

    def __hash__(self) -> int:
        return hash((self._cents, self.moneda))

    def is_negative(self) -> bool:
        return self._cents < 0

    def formatted(self) -> str:
        symbol = _SYMBOLS[self.moneda]
        amount = self.amount
        sign = "-" if amount < 0 else ""
        entero, _, decimales = f"{abs(amount):.2f}".partition(".")
        entero_con_miles = f"{int(entero):,}".replace(",", ".")
        return f"{sign}{symbol} {entero_con_miles},{decimales}"

    def __repr__(self) -> str:
        return f"Money({self._cents}, {self.moneda.value})"

    def __str__(self) -> str:
        return self.formatted()


def split_in_installments(total: Money, cantidad_cuotas: int) -> list[Money]:
    """Divide un monto total en N cuotas enteras (en centavos), sin perder centavos
    por redondeo: el resto se distribuye en las primeras cuotas."""
    if cantidad_cuotas <= 0:
        raise ValueError("La cantidad de cuotas debe ser mayor a cero")
    base, resto = divmod(total.cents, cantidad_cuotas)
    cuotas = []
    for i in range(cantidad_cuotas):
        extra = 1 if i < resto else 0
        cuotas.append(Money(base + extra, total.moneda))
    return cuotas
