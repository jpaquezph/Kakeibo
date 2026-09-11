from decimal import Decimal

import pytest

from home_budget.app.domain.money import CurrencyMismatchError, Money, Moneda, split_in_installments


def test_from_decimal_no_pierde_precision():
    m = Money.from_decimal("1234.56", Moneda.ARS)
    assert m.cents == 123456
    assert m.amount == Decimal("1234.56")


def test_suma_misma_moneda():
    a = Money.from_decimal("100.00", Moneda.ARS)
    b = Money.from_decimal("50.50", Moneda.ARS)
    assert (a + b).amount == Decimal("150.50")


def test_no_permite_mezclar_monedas():
    ars = Money.from_decimal("100", Moneda.ARS)
    usd = Money.from_decimal("100", Moneda.USD)
    with pytest.raises(CurrencyMismatchError):
        ars + usd
    with pytest.raises(CurrencyMismatchError):
        ars - usd
    with pytest.raises(CurrencyMismatchError):
        ars < usd


def test_split_in_installments_no_pierde_centavos():
    total = Money.from_decimal("100.00", Moneda.ARS)
    cuotas = split_in_installments(total, 3)
    assert sum(c.cents for c in cuotas) == total.cents
    assert [c.cents for c in cuotas] == [3334, 3333, 3333]


def test_formatted_usa_separador_argentino():
    m = Money.from_decimal("1234567.89", Moneda.ARS)
    assert m.formatted() == "$ 1.234.567,89"
