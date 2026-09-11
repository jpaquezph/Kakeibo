"""Utilidades de fechas sin dependencias externas."""
from __future__ import annotations

import calendar
from datetime import date


def add_months(base: date, months: int) -> date:
    """Suma `months` meses a `base`, ajustando el dia si el mes destino es mas corto."""
    total_month_index = base.month - 1 + months
    year = base.year + total_month_index // 12
    month = total_month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base.day, last_day)
    return date(year, month, day)
