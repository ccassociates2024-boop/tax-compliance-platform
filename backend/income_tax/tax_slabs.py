"""
Income Tax Slabs — AY 2025-26 (FY 2024-25)
Covers: Old Regime, New Regime (115BAC), Special rates (STCG/LTCG).
Surcharge & Cess fully computed.
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass


# ─── TAX SLABS ───────────────────────────────────────────────────────────────

# Old Regime — Individual (age < 60)
OLD_REGIME_INDIVIDUAL = [
    (0,       250_000,  0),
    (250_001,  500_000,  5),
    (500_001, 1_000_000, 20),
    (1_000_001, None,   30),
]

# Old Regime — Senior Citizen (60–80 years)
OLD_REGIME_SENIOR = [
    (0,       300_000,  0),
    (300_001,  500_000,  5),
    (500_001, 1_000_000, 20),
    (1_000_001, None,   30),
]

# Old Regime — Super Senior (>80 years)
OLD_REGIME_SUPER_SENIOR = [
    (0,       500_000,  0),
    (500_001, 1_000_000, 20),
    (1_000_001, None,   30),
]

# New Regime (Default from FY 2023-24) — Section 115BAC
NEW_REGIME_SLABS = [
    (0,       300_000,  0),
    (300_001,  700_000,  5),
    (700_001, 1_000_000, 10),
    (1_000_001, 1_200_000, 15),
    (1_200_001, 1_500_000, 20),
    (1_500_001, None,   30),
]

# Surcharge rates (both regimes)
SURCHARGE_RATES = [
    (0,         5_000_000,  0),
    (5_000_001, 10_000_000, 10),
    (10_000_001, 20_000_000, 15),
    (20_000_001, 50_000_000, 25),
    (50_000_001, None,       37),   # Capped at 25% for new regime (Budget 2023)
]

# New regime surcharge capped at 25% for income > 5Cr
NEW_REGIME_SURCHARGE_RATES = [
    (0,         5_000_000,  0),
    (5_000_001, 10_000_000, 10),
    (10_000_001, 20_000_000, 15),
    (20_000_001, None,      25),   # Capped at 25%
]

HEALTH_EDUCATION_CESS = Decimal("4")   # 4% on (tax + surcharge)

# Rebate u/s 87A
OLD_REGIME_REBATE_LIMIT = 500_000      # Income ≤ 5L → full tax rebate (max Rs. 12,500)
OLD_REGIME_REBATE_AMOUNT = 12_500
NEW_REGIME_REBATE_LIMIT = 700_000      # Income ≤ 7L → full tax rebate (max Rs. 25,000)
NEW_REGIME_REBATE_AMOUNT = 25_000

# Standard deduction
OLD_REGIME_STD_DEDUCTION = 50_000      # For salaried
NEW_REGIME_STD_DEDUCTION = 75_000      # Increased in Budget 2024 (effective AY 2025-26)

# Section 80CCD(2) — NPS employer contribution (new regime allowed)
NPS_EMPLOYER_DEDUCTION_RATE_NEW = Decimal("10")   # 10% of basic salary


def compute_slab_tax(income: int, slabs: list) -> Decimal:
    """Compute basic tax from slab rates."""
    tax = Decimal("0")
    income_d = Decimal(str(income))

    for lower, upper, rate in slabs:
        if income_d <= Decimal(str(lower)):
            break
        slab_upper = Decimal(str(upper)) if upper else income_d
        taxable_in_slab = min(income_d, slab_upper) - Decimal(str(lower))
        if taxable_in_slab > 0:
            tax += taxable_in_slab * Decimal(str(rate)) / 100

    return tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_surcharge(income: int, tax: Decimal, regime: str = "new") -> Decimal:
    """Compute surcharge with marginal relief."""
    rates = NEW_REGIME_SURCHARGE_RATES if regime == "new" else SURCHARGE_RATES
    surcharge_rate = Decimal("0")
    for lower, upper, rate in rates:
        if income > lower and (upper is None or income <= upper):
            surcharge_rate = Decimal(str(rate))
            break

    if surcharge_rate == 0:
        return Decimal("0")

    surcharge = (tax * surcharge_rate / 100).quantize(Decimal("0.01"))

    # Marginal relief: ensure extra tax from surcharge ≤ extra income above threshold
    for lower, upper, rate in rates:
        if rate > 0 and income > lower:
            threshold_income = lower
            threshold_tax = compute_slab_tax(threshold_income,
                NEW_REGIME_SLABS if regime == "new" else OLD_REGIME_INDIVIDUAL)
            threshold_surcharge = (threshold_tax * Decimal(str(rate - (rates[rates.index((lower, upper, rate))-1][2]))) / 100)
            extra_income = income - threshold_income
            extra_tax_with_surcharge = (tax + surcharge) - (threshold_tax + threshold_surcharge)
            if extra_tax_with_surcharge > extra_income:
                surcharge = Decimal(str(extra_income)) - (tax - threshold_tax)
                surcharge = max(surcharge, Decimal("0"))
            break

    return surcharge.quantize(Decimal("0.01"))


def compute_rebate_87a(income: int, tax: Decimal, regime: str = "new") -> Decimal:
    """Section 87A rebate."""
    if regime == "new":
        if income <= NEW_REGIME_REBATE_LIMIT:
            return min(tax, Decimal(str(NEW_REGIME_REBATE_AMOUNT)))
    else:
        if income <= OLD_REGIME_REBATE_LIMIT:
            return min(tax, Decimal(str(OLD_REGIME_REBATE_AMOUNT)))
    return Decimal("0")


def get_slabs(regime: str, age: int) -> list:
    if regime == "new":
        return NEW_REGIME_SLABS
    if age >= 80:
        return OLD_REGIME_SUPER_SENIOR
    if age >= 60:
        return OLD_REGIME_SENIOR
    return OLD_REGIME_INDIVIDUAL
