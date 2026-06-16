"""
ITR Computation Engine — AY 2025-26
Full income tax computation: income aggregation, deductions, tax, advance tax,
Old vs New regime comparison, ITR form selection.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from enum import Enum

from .tax_slabs import (
    compute_slab_tax, compute_surcharge, compute_rebate_87a, get_slabs,
    HEALTH_EDUCATION_CESS,
)
from .deductions import DeductionInput, DeductionComputer, DeductionResult


# ─── ITR FORM CONSTANTS ────────────────────────────────────────────────────────

class ITRForm(str, Enum):
    ITR1 = "ITR-1"    # Sahaj — salaried, one house, other sources ≤ 50L
    ITR2 = "ITR-2"    # Capital gains, multiple properties, foreign assets
    ITR3 = "ITR-3"    # Business/profession income
    ITR4 = "ITR-4"    # Presumptive taxation (44AD/44ADA/44AE)
    ITR5 = "ITR-5"    # Firms, LLP, AOP, BOI
    ITR6 = "ITR-6"    # Companies (not claiming 11/12 exemption)
    ITR7 = "ITR-7"    # Trusts, political parties, research institutions


# ─── INPUT DATACLASSES ────────────────────────────────────────────────────────

@dataclass
class SalaryIncome:
    gross_salary: float = 0          # CTC / gross salary
    basic_salary: float = 0
    hra_component: float = 0         # HRA paid by employer (forms part of gross)
    special_allowances: float = 0
    lta_component: float = 0
    other_allowances: float = 0
    perquisites: float = 0           # Taxable perks

    # Exempt allowances (pre-computed by employer in Form 16)
    hra_exempt: float = 0
    lta_exempt: float = 0
    other_exempt_allowances: float = 0

    # TDS deducted by employer
    tds_by_employer: float = 0


@dataclass
class HousePropertyIncome:
    """Per property income/loss computation."""
    annual_letable_value: float = 0      # Actual rent received / expected rent
    municipal_tax_paid: float = 0
    home_loan_interest: float = 0        # Section 24(b)
    is_self_occupied: bool = True
    property_type: str = "self_occupied" # self_occupied | let_out | deemed_let_out

    @property
    def net_annual_value(self) -> float:
        if self.is_self_occupied:
            return 0.0
        return max(0.0, self.annual_letable_value - self.municipal_tax_paid)

    @property
    def standard_deduction_30pct(self) -> float:
        return self.net_annual_value * 0.30

    @property
    def income_from_hp(self) -> float:
        nav = self.net_annual_value
        std_ded = self.standard_deduction_30pct
        interest_limit = self.home_loan_interest  # No limit for let-out
        if self.is_self_occupied:
            interest_limit = min(self.home_loan_interest, 200_000)
        return nav - std_ded - interest_limit


@dataclass
class CapitalGainsIncome:
    # Short-term capital gains
    stcg_111a: float = 0      # Listed equity/equity MF (15%)
    stcg_other: float = 0     # Other assets (slab rate)

    # Long-term capital gains
    ltcg_112a: float = 0      # Listed equity > 1L (10% without indexation)
    ltcg_other: float = 0     # Other assets (20% with indexation)
    ltcg_112a_exempt: float = 100_000  # Exempt up to 1L u/s 112A


@dataclass
class BusinessIncome:
    net_profit: float = 0
    # Presumptive basis (44AD / 44ADA / 44AE)
    is_presumptive: bool = False
    presumptive_section: str = ""    # 44AD / 44ADA / 44AE
    turnover: float = 0
    presumptive_rate: float = 0      # 6% / 8% / 50%


@dataclass
class OtherSourcesIncome:
    interest_savings: float = 0
    interest_fd: float = 0
    interest_other: float = 0
    dividend: float = 0
    family_pension: float = 0       # 1/3rd or 15K std deduction allowed
    gifts_taxable: float = 0
    other: float = 0


@dataclass
class AdvanceTaxPaid:
    q1_june: float = 0      # Due 15 Jun (15% of estimated tax)
    q2_sep: float = 0       # Due 15 Sep (cumulative 45%)
    q3_dec: float = 0       # Due 15 Dec (cumulative 75%)
    q4_march: float = 0     # Due 15 Mar (100%)

    @property
    def total(self) -> float:
        return self.q1_june + self.q2_sep + self.q3_dec + self.q4_march


@dataclass
class TDSCredit:
    tds_salary: float = 0           # From Form 16
    tds_26as_other: float = 0       # From Form 26AS (FDs, contracts, etc.)
    tcs_collected: float = 0        # Tax collected at source


@dataclass
class ITRInput:
    """Complete ITR input for AY 2025-26."""
    # Taxpayer profile
    pan: str = ""
    name: str = ""
    age: int = 30
    entity_type: str = "individual"   # individual / HUF / firm / company

    # Income heads
    salary: SalaryIncome = field(default_factory=SalaryIncome)
    house_properties: list = field(default_factory=list)   # list[HousePropertyIncome]
    capital_gains: CapitalGainsIncome = field(default_factory=CapitalGainsIncome)
    business: BusinessIncome = field(default_factory=BusinessIncome)
    other_sources: OtherSourcesIncome = field(default_factory=OtherSourcesIncome)

    # Deduction inputs
    deductions: DeductionInput = field(default_factory=DeductionInput)

    # Tax payments
    advance_tax: AdvanceTaxPaid = field(default_factory=AdvanceTaxPaid)
    tds: TDSCredit = field(default_factory=TDSCredit)
    self_assessment_tax: float = 0

    # Regime preference
    preferred_regime: str = "auto"   # auto / old / new


# ─── OUTPUT DATACLASSES ───────────────────────────────────────────────────────

@dataclass
class IncomeHeadSummary:
    salary_taxable: float = 0
    house_property: float = 0        # Can be negative (loss up to 2L allowed)
    business_income: float = 0
    stcg_111a: float = 0
    stcg_other: float = 0
    ltcg_112a_taxable: float = 0
    ltcg_other: float = 0
    other_sources: float = 0
    gross_total_income: float = 0


@dataclass
class TaxComputation:
    regime: str
    gross_total_income: float
    total_deductions: float
    taxable_income: float
    basic_tax: float
    tax_on_stcg_111a: float = 0
    tax_on_ltcg_112a: float = 0
    tax_on_ltcg_other: float = 0
    total_tax_before_surcharge: float = 0
    surcharge: float = 0
    health_edu_cess: float = 0
    total_tax_liability: float = 0
    rebate_87a: float = 0
    net_tax_payable: float = 0

    # Tax credits
    advance_tax_paid: float = 0
    tds_credit: float = 0
    self_assessment_tax: float = 0
    total_tax_paid: float = 0

    # Final result
    tax_payable_refundable: float = 0   # Positive = payable, negative = refund

    # Deduction details
    deduction_result: DeductionResult = field(default_factory=DeductionResult)


@dataclass
class RegimeComparison:
    old_regime: TaxComputation
    new_regime: TaxComputation
    recommended_regime: str
    savings: float                   # Positive = old saves more, negative = new saves more
    recommendation_reason: str


@dataclass
class ITRResult:
    itr_form: ITRForm
    itr_form_reason: str
    income_summary: IncomeHeadSummary
    old_regime: TaxComputation
    new_regime: TaxComputation
    comparison: RegimeComparison
    optimal_regime: TaxComputation   # The better one
    advance_tax_schedule: dict       # Quarterly breakup for current year
    deduction_optimizer_tips: list   # Tips to increase savings


# ─── ENGINE ───────────────────────────────────────────────────────────────────

class ITREngine:
    """
    Main Income Tax Return computation engine — AY 2025-26 (FY 2024-25).
    Call compute() with an ITRInput to get a full ITRResult.
    """

    def __init__(self):
        self._deduction_computer = DeductionComputer()

    def compute(self, inp: ITRInput) -> ITRResult:
        income = self._compute_income_heads(inp)
        itr_form, itr_reason = self._select_itr_form(inp, income)

        old = self._compute_tax(inp, income, "old")
        new = self._compute_tax(inp, income, "new")

        comparison = self._compare_regimes(old, new)
        optimal = old if comparison.recommended_regime == "old" else new

        advance_tax = self._advance_tax_schedule(optimal.net_tax_payable)
        tips = self._deduction_optimizer_tips(inp, income, old, new)

        return ITRResult(
            itr_form=itr_form,
            itr_form_reason=itr_reason,
            income_summary=income,
            old_regime=old,
            new_regime=new,
            comparison=comparison,
            optimal_regime=optimal,
            advance_tax_schedule=advance_tax,
            deduction_optimizer_tips=tips,
        )

    # ── Income Heads ──────────────────────────────────────────────────────────

    def _compute_income_heads(self, inp: ITRInput) -> IncomeHeadSummary:
        s = IncomeHeadSummary()

        # Salary — gross minus exempt allowances
        sal = inp.salary
        s.salary_taxable = max(
            0,
            sal.gross_salary - sal.hra_exempt - sal.lta_exempt - sal.other_exempt_allowances
        )

        # House Property — aggregate all properties, cap loss at 2L
        hp_total = sum(p.income_from_hp for p in inp.house_properties)
        s.house_property = max(hp_total, -200_000)   # Set-off limit

        # Business / Profession
        if inp.business.net_profit or inp.business.is_presumptive:
            if inp.business.is_presumptive and inp.business.turnover:
                s.business_income = inp.business.turnover * inp.business.presumptive_rate / 100
            else:
                s.business_income = inp.business.net_profit
        else:
            s.business_income = 0

        # Capital Gains (separately taxed — not included in GTI for slab)
        s.stcg_111a = inp.capital_gains.stcg_111a
        s.stcg_other = inp.capital_gains.stcg_other
        ltcg_112a_gross = inp.capital_gains.ltcg_112a
        s.ltcg_112a_taxable = max(0, ltcg_112a_gross - inp.capital_gains.ltcg_112a_exempt)
        s.ltcg_other = inp.capital_gains.ltcg_other

        # Other Sources
        os = inp.other_sources
        family_pension_std_ded = min(os.family_pension / 3, 15_000)
        s.other_sources = (
            os.interest_savings + os.interest_fd + os.interest_other +
            os.dividend + os.gifts_taxable + os.other +
            max(0, os.family_pension - family_pension_std_ded)
        )

        # Gross Total Income = all heads EXCEPT separately taxed CG
        s.gross_total_income = (
            s.salary_taxable +
            s.house_property +
            s.business_income +
            s.stcg_other +       # Non-111A STCG taxed at slab
            s.other_sources
        )
        # GTI cannot be negative
        s.gross_total_income = max(0, s.gross_total_income)

        return s

    # ── Tax Computation ───────────────────────────────────────────────────────

    def _compute_tax(self, inp: ITRInput, income: IncomeHeadSummary, regime: str) -> TaxComputation:
        ded_result = self._deduction_computer.compute(
            inp.deductions, regime, inp.age, income.gross_total_income
        )

        taxable = max(0, income.gross_total_income - ded_result.grand_total_deductions)

        # Tax on normal slab income
        slabs = get_slabs(regime, inp.age)
        basic_tax = float(compute_slab_tax(int(taxable), slabs))

        # Special rate taxes
        stcg_111a_tax = income.stcg_111a * 0.15
        ltcg_112a_tax = income.ltcg_112a_taxable * 0.10
        ltcg_other_tax = income.ltcg_other * 0.20   # With indexation benefit

        total_before_surcharge = basic_tax + stcg_111a_tax + ltcg_112a_tax + ltcg_other_tax

        # Surcharge on normal income (STCG/LTCG capped at 15% surcharge)
        surcharge_income = taxable + income.stcg_111a + income.ltcg_112a_taxable + income.ltcg_other
        surcharge = float(compute_surcharge(int(surcharge_income), Decimal(str(total_before_surcharge)), regime))

        cess = float((Decimal(str(total_before_surcharge + surcharge)) * HEALTH_EDUCATION_CESS / 100)
                     .quantize(Decimal("0.01")))

        total_tax = total_before_surcharge + surcharge + cess

        # 87A rebate (only on normal slab income — not on STCG 111A / LTCG)
        rebate = float(compute_rebate_87a(int(taxable), Decimal(str(basic_tax)), regime))
        net_tax = max(0, total_tax - rebate)

        # Tax credits
        tds_total = inp.tds.tds_salary + inp.tds.tds_26as_other + inp.tds.tcs_collected
        total_paid = inp.advance_tax.total + tds_total + inp.self_assessment_tax
        final = net_tax - total_paid  # Positive = payable, negative = refund

        tc = TaxComputation(
            regime=regime,
            gross_total_income=income.gross_total_income,
            total_deductions=ded_result.grand_total_deductions,
            taxable_income=taxable,
            basic_tax=basic_tax,
            tax_on_stcg_111a=stcg_111a_tax,
            tax_on_ltcg_112a=ltcg_112a_tax,
            tax_on_ltcg_other=ltcg_other_tax,
            total_tax_before_surcharge=total_before_surcharge,
            surcharge=surcharge,
            health_edu_cess=cess,
            total_tax_liability=total_tax,
            rebate_87a=rebate,
            net_tax_payable=net_tax,
            advance_tax_paid=inp.advance_tax.total,
            tds_credit=tds_total,
            self_assessment_tax=inp.self_assessment_tax,
            total_tax_paid=total_paid,
            tax_payable_refundable=final,
            deduction_result=ded_result,
        )
        return tc

    # ── Regime Comparison ─────────────────────────────────────────────────────

    def _compare_regimes(self, old: TaxComputation, new: TaxComputation) -> RegimeComparison:
        savings = old.net_tax_payable - new.net_tax_payable  # Positive = new saves money

        if new.net_tax_payable < old.net_tax_payable:
            recommended = "new"
            reason = (
                f"New Regime saves ₹{abs(savings):,.0f} in tax. "
                "Your deductions are insufficient to offset the benefit of lower new-regime slabs."
            )
        elif old.net_tax_payable < new.net_tax_payable:
            recommended = "old"
            reason = (
                f"Old Regime saves ₹{abs(savings):,.0f} in tax. "
                "Your Chapter VI-A deductions (80C, 80D, HRA, etc.) significantly reduce taxable income."
            )
        else:
            recommended = "new"
            reason = "Both regimes result in the same tax. New Regime recommended for simplicity."

        return RegimeComparison(
            old_regime=old,
            new_regime=new,
            recommended_regime=recommended,
            savings=abs(savings),
            recommendation_reason=reason,
        )

    # ── ITR Form Selector ─────────────────────────────────────────────────────

    def _select_itr_form(self, inp: ITRInput, income: IncomeHeadSummary) -> tuple[ITRForm, str]:
        entity = inp.entity_type.lower()

        if entity in ("firm", "llp", "aop", "boi"):
            return ITRForm.ITR5, "Firms, LLPs, AOPs, and BOIs must file ITR-5."

        if entity == "company":
            return ITRForm.ITR6, "Companies (other than those claiming exemption u/s 11) must file ITR-6."

        if entity in ("trust", "political_party", "institution"):
            return ITRForm.ITR7, "Charitable trusts, political parties, and research institutions file ITR-7."

        # For individual / HUF
        has_business = inp.business.net_profit > 0 or inp.business.is_presumptive
        has_capital_gains = (income.stcg_111a + income.stcg_other +
                             income.ltcg_112a_taxable + income.ltcg_other) > 0
        has_foreign_assets = False  # would need a flag in ITRInput
        has_multiple_hp = len(inp.house_properties) > 1
        total_income_all = (income.gross_total_income + income.stcg_111a +
                            income.ltcg_112a_taxable + income.ltcg_other)

        if has_business and inp.business.is_presumptive:
            return ITRForm.ITR4, (
                f"Presumptive taxation u/s {inp.business.presumptive_section or '44AD/44ADA/44AE'} — "
                "ITR-4 (Sugam) applies."
            )

        if has_business:
            return ITRForm.ITR3, (
                "Income from business or profession (other than presumptive) — ITR-3 is mandatory."
            )

        if entity == "huf":
            return ITRForm.ITR2, "HUFs with no business income file ITR-2."

        # Individual without business income
        if has_capital_gains or has_foreign_assets or has_multiple_hp:
            reasons = []
            if has_capital_gains:
                reasons.append("capital gains income")
            if has_multiple_hp:
                reasons.append("more than one house property")
            if has_foreign_assets:
                reasons.append("foreign assets")
            return ITRForm.ITR2, f"ITR-2 required due to: {', '.join(reasons)}."

        if total_income_all > 5_000_000:
            return ITRForm.ITR2, "Total income exceeds ₹50 lakhs — ITR-2 is required."

        if len(inp.house_properties) > 1:
            return ITRForm.ITR2, "More than one house property — ITR-2 required."

        # ITR-1 eligibility: salaried, one HP, other sources, total ≤ 50L
        return ITRForm.ITR1, (
            "Salaried individual with income from salary, one house property, and other sources "
            "with total income up to ₹50 lakhs — ITR-1 (Sahaj) applies."
        )

    # ── Advance Tax Schedule ──────────────────────────────────────────────────

    def _advance_tax_schedule(self, estimated_tax: float) -> dict:
        """
        Advance tax installment schedule for FY 2025-26 (AY 2026-27).
        Percentages: 15% by Jun-15, 45% by Sep-15, 75% by Dec-15, 100% by Mar-15.
        """
        if estimated_tax <= 10_000:
            return {
                "applicable": False,
                "note": "Advance tax not applicable — estimated tax liability ≤ ₹10,000.",
            }

        return {
            "applicable": True,
            "estimated_annual_tax": round(estimated_tax, 2),
            "installments": [
                {
                    "due_date": "15 June 2025",
                    "cumulative_pct": 15,
                    "amount_due": round(estimated_tax * 0.15, 2),
                    "quarter": "Q1",
                },
                {
                    "due_date": "15 September 2025",
                    "cumulative_pct": 45,
                    "amount_due": round(estimated_tax * 0.30, 2),   # Additional 30%
                    "quarter": "Q2",
                },
                {
                    "due_date": "15 December 2025",
                    "cumulative_pct": 75,
                    "amount_due": round(estimated_tax * 0.30, 2),   # Additional 30%
                    "quarter": "Q3",
                },
                {
                    "due_date": "15 March 2026",
                    "cumulative_pct": 100,
                    "amount_due": round(estimated_tax * 0.25, 2),   # Final 25%
                    "quarter": "Q4",
                },
            ],
            "note": "Interest u/s 234B/234C applicable if installments are short/late.",
        }

    # ── Deduction Optimizer Tips ──────────────────────────────────────────────

    def _deduction_optimizer_tips(self, inp: ITRInput, income: IncomeHeadSummary,
                                   old: TaxComputation, new: TaxComputation) -> list:
        tips = []
        d = inp.deductions
        ded = old.deduction_result

        # 80C gap
        gross_80c = ded.gross_80c
        if gross_80c < DeductionComputer.LIMIT_80C:
            gap = DeductionComputer.LIMIT_80C - gross_80c
            tips.append({
                "section": "80C",
                "tip": f"You have ₹{gap:,.0f} unused 80C room. Invest in ELSS, PPF, NPS, or 5-year FD to save "
                       f"up to ₹{gap * 0.30:,.0f} in tax (at 30% slab).",
                "potential_saving": round(gap * 0.30),
            })

        # 80CCD(1B) — NPS
        if d.nps_additional_80ccd1b < DeductionComputer.LIMIT_80CCD1B:
            gap = DeductionComputer.LIMIT_80CCD1B - d.nps_additional_80ccd1b
            tips.append({
                "section": "80CCD(1B)",
                "tip": f"₹{gap:,.0f} additional NPS contribution can save ₹{gap * 0.30:,.0f} extra (over 80C cap).",
                "potential_saving": round(gap * 0.30),
            })

        # 80D — mediclaim
        if d.mediclaim_self_family == 0:
            tips.append({
                "section": "80D",
                "tip": "No mediclaim premium entered. Purchase health insurance for self/family to claim "
                       "deduction up to ₹25,000 (₹50,000 if senior citizen).",
                "potential_saving": round(25_000 * 0.30),
            })

        # HRA — if rent paid but no HRA claimed
        if d.rent_paid_actual > 0 and d.hra_received == 0 and d.rent_paid_80gg == 0:
            tips.append({
                "section": "80GG",
                "tip": "You pay rent but have no HRA from employer. Consider claiming deduction u/s 80GG.",
                "potential_saving": None,
            })

        # Home loan — 24(b)
        if d.home_loan_interest_24b == 0:
            tips.append({
                "section": "24(b)",
                "tip": "No home loan interest entered. If you have a home loan, claim interest deduction "
                       "up to ₹2,00,000 for self-occupied property.",
                "potential_saving": round(200_000 * 0.30),
            })

        # 80D — parents
        if d.mediclaim_parents == 0:
            tips.append({
                "section": "80D (Parents)",
                "tip": "No parent mediclaim premium entered. Senior parent coverage adds up to ₹50,000 deduction.",
                "potential_saving": round(50_000 * 0.30),
            })

        # Regime switch
        savings = abs(old.net_tax_payable - new.net_tax_payable)
        if savings > 0:
            better = "New" if new.net_tax_payable < old.net_tax_payable else "Old"
            tips.append({
                "section": "Regime",
                "tip": f"{better} Regime saves ₹{savings:,.0f}. Switch regime to optimise tax.",
                "potential_saving": round(savings),
            })

        return tips


# ─── CONVENIENCE FUNCTION ─────────────────────────────────────────────────────

def compute_itr(inp: ITRInput) -> ITRResult:
    return ITREngine().compute(inp)
