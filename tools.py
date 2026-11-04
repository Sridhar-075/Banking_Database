from decimal import Decimal, ROUND_HALF_UP
from datetime import date
import calendar

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_emi(
    principal: Decimal,
    monthly_rate: Decimal,
    tenure: int
) -> Decimal:

    if monthly_rate == 0:
        return money(principal / tenure)

    factor = (Decimal("1") + monthly_rate) ** tenure

    emi = (
        principal
        * monthly_rate
        * factor
        / (factor - Decimal("1"))
    )

    return money(emi)

def add_months(original_date: date, months: int) -> date:
    month_index = original_date.month - 1 + months

    year = original_date.year + month_index // 12
    month = month_index % 12 + 1

    day = min(
        original_date.day,
        calendar.monthrange(year, month)[1]
    )

    return date(year, month, day)