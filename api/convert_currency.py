"""
Simple, deterministic FX helpers for JOD/USD/EUR conversions.
All conversions are rounded to 2 decimal places using bankers' rounding.
"""

from decimal import Decimal, ROUND_HALF_UP

RATES = {
    'USD_PER_JOD': Decimal('1.41'),
    'EUR_PER_JOD': Decimal('1.31'),
}


def jod_to_usd(amount: Decimal) -> Decimal:
    return (amount * RATES['USD_PER_JOD']).quantize(Decimal('0.01'),
                                                    rounding=ROUND_HALF_UP)


def usd_to_jod(amount: Decimal) -> Decimal:
    return (amount / RATES['USD_PER_JOD']).quantize(Decimal('0.01'),
                                                    rounding=ROUND_HALF_UP)


def jod_to_eur(amount: Decimal) -> Decimal:
    return (amount * RATES['EUR_PER_JOD']).quantize(Decimal('0.01'),
                                                    rounding=ROUND_HALF_UP)


def eur_to_jod(amount: Decimal) -> Decimal:
    return (amount / RATES['EUR_PER_JOD']).quantize(Decimal('0.01'),
                                                    rounding=ROUND_HALF_UP)


def usd_to_eur(amount: Decimal) -> Decimal:
    """Convert USD to EUR via JOD intermediary."""
    jod_amount = usd_to_jod(amount)
    return jod_to_eur(jod_amount)


def eur_to_usd(amount: Decimal) -> Decimal:
    """Convert EUR to USD via JOD intermediary."""
    jod_amount = eur_to_jod(amount)
    return jod_to_usd(jod_amount)

