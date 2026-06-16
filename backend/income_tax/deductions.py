"""
Income Tax Deductions — Chapter VI-A and Under-Head deductions.
AY 2025-26 / FY 2024-25 limits applied.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class DeductionInput:
    """All possible deduction inputs from the taxpayer."""
    # ── Chapter VI-A ──────────────────────────────────────────────────────────
    # Section 80C (max 1,50,000)
    lic_premium: float = 0
    ppf: float = 0
    epf: float = 0
    elss: float = 0
    home_loan_principal: float = 0
    nsc: float = 0
    tuition_fees: float = 0         # Max 2 children
    five_yr_fd: float = 0           # 5-year bank FD
    sukanya_samriddhi: float = 0
    ulip: float = 0
    nabard_bonds: float = 0
    stamp_duty_registration: float = 0
    senior_citizen_savings: float = 0
    other_80c: float = 0

    # Section 80CCC — Pension fund premium
    pension_fund_80ccc: float = 0

    # Section 80CCD(1) — NPS (employee contribution, within 80C limit)
    nps_employee_80ccd1: float = 0

    # Section 80CCD(1B) — NPS additional (max 50,000, OVER 80C)
    nps_additional_80ccd1b: float = 0

    # Section 80CCD(2) — NPS employer contribution (no limit, not in 80C)
    nps_employer_80ccd2: float = 0

    # Section 80D — Medical insurance
    mediclaim_self_family: float = 0        # Max 25K (50K if self/spouse senior)
    mediclaim_self_senior: bool = False      # Self/spouse is senior citizen
    mediclaim_parents: float = 0            # Max 25K (50K if parents senior)
    mediclaim_parents_senior: bool = False   # Parents are senior citizens
    preventive_health_checkup: float = 0    # Max 5K (within 80D limit)

    # Section 80DD — Disabled dependent (75K/1.25L)
    disability_80dd: float = 0
    severe_disability_80dd: bool = False

    # Section 80DDB — Medical treatment (40K/1L senior)
    medical_treatment_80ddb: float = 0
    is_senior_80ddb: bool = False

    # Section 80E — Education loan interest
    education_loan_interest: float = 0     # No limit, 8 years

    # Section 80EE — Additional home loan interest (first-time buyer)
    additional_home_loan_interest_80ee: float = 0  # Max 50K

    # Section 80EEA — Additional home loan (affordable housing)
    additional_home_loan_80eea: float = 0          # Max 1.5L

    # Section 80G — Donations
    donation_100_percent: float = 0        # PM Relief, etc.
    donation_50_percent: float = 0         # Other approved funds
    donation_100_csr: float = 0           # 100% with qualifying limit
    donation_50_qualifying: float = 0      # 50% with qualifying limit

    # Section 80GG — Rent paid (if no HRA)
    rent_paid_80gg: float = 0

    # Section 80TTA/TTB — Interest income
    savings_interest_80tta: float = 0      # Max 10K (non-senior)
    senior_interest_80ttb: float = 0       # Max 50K (senior citizens)

    # Section 80U — Own disability
    disability_80u: float = 0
    severe_disability_80u: bool = False

    # ── Under-Head Deductions (not Chapter VI-A) ───────────────────────────
    # Section 24(b) — Home loan interest
    home_loan_interest_24b: float = 0      # Max 2L self-occupied; no limit let-out

    # HRA Exemption inputs (computed separately)
    hra_received: float = 0
    basic_da_for_hra: float = 0
    rent_paid_actual: float = 0
    is_metro: bool = False

    # Standard Deduction (auto-applied for salaried)
    is_salaried: bool = True

    # Professional Tax
    professional_tax: float = 0            # Actual amount paid

    # LTA (Leave Travel Allowance)
    lta_exemption: float = 0


@dataclass
class DeductionResult:
    """Computed deduction amounts."""
    # 80C block
    gross_80c: float = 0
    eligible_80c: float = 0               # Min(gross, 1,50,000)
    eligible_80ccd1b: float = 0           # Min(NPS additional, 50,000)
    eligible_80ccd2: float = 0            # NPS employer (no cap)
    total_80c_block: float = 0

    # 80D
    eligible_80d_self: float = 0
    eligible_80d_parents: float = 0
    total_80d: float = 0

    # Other deductions
    eligible_80dd: float = 0
    eligible_80ddb: float = 0
    eligible_80e: float = 0
    eligible_80ee: float = 0
    eligible_80eea: float = 0
    eligible_80g: float = 0
    eligible_80gg: float = 0
    eligible_80tta_ttb: float = 0
    eligible_80u: float = 0

    # Under-head
    hra_exemption: float = 0
    home_loan_interest_deduction: float = 0
    standard_deduction: float = 0
    professional_tax_deduction: float = 0
    lta_exemption: float = 0

    # Grand total
    total_chapter_via: float = 0
    total_under_head: float = 0
    grand_total_deductions: float = 0

    # Breakdown dict for display
    breakdown: dict = field(default_factory=dict)


class DeductionComputer:
    """Computes all applicable deductions with AY 2025-26 limits."""

    # Section 80C limits
    LIMIT_80C = 150_000
    LIMIT_80CCC = 150_000          # Part of 80C aggregate
    LIMIT_80CCD1B = 50_000         # Additional NPS (outside 80C)
    LIMIT_80D_SELF_NORMAL = 25_000
    LIMIT_80D_SELF_SENIOR = 50_000
    LIMIT_80D_PARENTS_NORMAL = 25_000
    LIMIT_80D_PARENTS_SENIOR = 50_000
    LIMIT_80D_PREVENTIVE = 5_000   # Within 80D limit
    LIMIT_80DD_NORMAL = 75_000
    LIMIT_80DD_SEVERE = 125_000
    LIMIT_80DDB_NORMAL = 40_000
    LIMIT_80DDB_SENIOR = 100_000
    LIMIT_80EE = 50_000
    LIMIT_80EEA = 150_000
    LIMIT_80GG_MONTHLY = 5_000     # Rs 5000/month max
    LIMIT_80TTA = 10_000
    LIMIT_80TTB = 50_000           # Senior citizens
    LIMIT_80U_NORMAL = 75_000
    LIMIT_80U_SEVERE = 125_000
    LIMIT_24B_SELF_OCC = 200_000   # Self-occupied property
    STD_DEDUCTION_OLD = 50_000
    STD_DEDUCTION_NEW = 75_000     # AY 2025-26 new regime

    def compute(self, inp: DeductionInput, regime: str, age: int, gross_income: float) -> DeductionResult:
        r = DeductionResult()

        if regime == "new":
            return self._compute_new_regime(inp, r, gross_income)

        return self._compute_old_regime(inp, r, age, gross_income)

    def _compute_old_regime(self, inp: DeductionInput, r: DeductionResult, age: int, gross_income: float) -> DeductionResult:
        # ── Standard Deduction ─────────────────────────────────────────────
        if inp.is_salaried:
            r.standard_deduction = self.STD_DEDUCTION_OLD
            r.breakdown["Standard Deduction (Sec 16)"] = r.standard_deduction

        # ── Professional Tax ───────────────────────────────────────────────
        r.professional_tax_deduction = min(inp.professional_tax, 2500)
        if r.professional_tax_deduction:
            r.breakdown["Professional Tax (Sec 16(iii))"] = r.professional_tax_deduction

        # ── HRA Exemption ──────────────────────────────────────────────────
        if inp.hra_received > 0 and inp.rent_paid_actual > 0:
            r.hra_exemption = self._compute_hra(inp)
            if r.hra_exemption:
                r.breakdown["HRA Exemption (Sec 10(13A))"] = r.hra_exemption

        # ── LTA ────────────────────────────────────────────────────────────
        r.lta_exemption = inp.lta_exemption
        if r.lta_exemption:
            r.breakdown["LTA Exemption (Sec 10(5))"] = r.lta_exemption

        # ── Section 24(b) Home Loan Interest ───────────────────────────────
        r.home_loan_interest_deduction = min(inp.home_loan_interest_24b, self.LIMIT_24B_SELF_OCC)
        if r.home_loan_interest_deduction:
            r.breakdown["Home Loan Interest (Sec 24(b))"] = r.home_loan_interest_deduction

        # ── 80C Block ──────────────────────────────────────────────────────
        gross_80c = (inp.lic_premium + inp.ppf + inp.epf + inp.elss +
                     inp.home_loan_principal + inp.nsc + inp.tuition_fees +
                     inp.five_yr_fd + inp.sukanya_samriddhi + inp.ulip +
                     inp.nabard_bonds + inp.stamp_duty_registration +
                     inp.senior_citizen_savings + inp.other_80c +
                     inp.pension_fund_80ccc + inp.nps_employee_80ccd1)
        r.gross_80c = gross_80c
        r.eligible_80c = min(gross_80c, self.LIMIT_80C)
        r.breakdown["80C/80CCC/80CCD(1)"] = r.eligible_80c

        r.eligible_80ccd1b = min(inp.nps_additional_80ccd1b, self.LIMIT_80CCD1B)
        if r.eligible_80ccd1b:
            r.breakdown["NPS Additional (Sec 80CCD(1B))"] = r.eligible_80ccd1b

        r.eligible_80ccd2 = inp.nps_employer_80ccd2   # No cap
        if r.eligible_80ccd2:
            r.breakdown["NPS Employer (Sec 80CCD(2))"] = r.eligible_80ccd2

        r.total_80c_block = r.eligible_80c + r.eligible_80ccd1b + r.eligible_80ccd2

        # ── Section 80D ────────────────────────────────────────────────────
        self_limit = self.LIMIT_80D_SELF_SENIOR if inp.mediclaim_self_senior else self.LIMIT_80D_SELF_NORMAL
        r.eligible_80d_self = min(inp.mediclaim_self_family + inp.preventive_health_checkup, self_limit)

        parents_limit = self.LIMIT_80D_PARENTS_SENIOR if inp.mediclaim_parents_senior else self.LIMIT_80D_PARENTS_NORMAL
        r.eligible_80d_parents = min(inp.mediclaim_parents, parents_limit)

        r.total_80d = r.eligible_80d_self + r.eligible_80d_parents
        if r.total_80d:
            r.breakdown["Medical Insurance (Sec 80D)"] = r.total_80d

        # ── Section 80DD ───────────────────────────────────────────────────
        if inp.disability_80dd > 0:
            r.eligible_80dd = self.LIMIT_80DD_SEVERE if inp.severe_disability_80dd else self.LIMIT_80DD_NORMAL
            r.breakdown["Disabled Dependent (Sec 80DD)"] = r.eligible_80dd

        # ── Section 80DDB ──────────────────────────────────────────────────
        if inp.medical_treatment_80ddb > 0:
            limit = self.LIMIT_80DDB_SENIOR if inp.is_senior_80ddb or age >= 60 else self.LIMIT_80DDB_NORMAL
            r.eligible_80ddb = min(inp.medical_treatment_80ddb, limit)
            r.breakdown["Medical Treatment (Sec 80DDB)"] = r.eligible_80ddb

        # ── Section 80E ────────────────────────────────────────────────────
        r.eligible_80e = inp.education_loan_interest   # No limit
        if r.eligible_80e:
            r.breakdown["Education Loan Interest (Sec 80E)"] = r.eligible_80e

        # ── Section 80EE / 80EEA ───────────────────────────────────────────
        r.eligible_80ee = min(inp.additional_home_loan_interest_80ee, self.LIMIT_80EE)
        r.eligible_80eea = min(inp.additional_home_loan_80eea, self.LIMIT_80EEA)
        if r.eligible_80ee:
            r.breakdown["Add. Home Loan Interest (Sec 80EE)"] = r.eligible_80ee
        if r.eligible_80eea:
            r.breakdown["Affordable Housing Loan (Sec 80EEA)"] = r.eligible_80eea

        # ── Section 80G ────────────────────────────────────────────────────
        qualifying_limit = gross_income * 0.10   # 10% of adjusted gross income
        g100 = inp.donation_100_percent
        g50 = inp.donation_50_percent * 0.5
        g100_ql = min(inp.donation_100_csr, qualifying_limit)
        g50_ql = min(inp.donation_50_qualifying * 0.5, qualifying_limit * 0.5)
        r.eligible_80g = g100 + g50 + g100_ql + g50_ql
        if r.eligible_80g:
            r.breakdown["Donations (Sec 80G)"] = r.eligible_80g

        # ── Section 80GG ───────────────────────────────────────────────────
        if inp.rent_paid_80gg > 0 and inp.hra_received == 0:
            monthly_rent = inp.rent_paid_80gg / 12
            monthly_limit = min(
                self.LIMIT_80GG_MONTHLY,
                gross_income * 0.25 / 12,
                monthly_rent - (gross_income * 0.10 / 12),
            )
            r.eligible_80gg = max(0, monthly_limit) * 12
            if r.eligible_80gg:
                r.breakdown["Rent Paid (Sec 80GG)"] = r.eligible_80gg

        # ── Section 80TTA / 80TTB ──────────────────────────────────────────
        if age >= 60:
            r.eligible_80tta_ttb = min(inp.senior_interest_80ttb, self.LIMIT_80TTB)
            if r.eligible_80tta_ttb:
                r.breakdown["Interest Income - Senior (Sec 80TTB)"] = r.eligible_80tta_ttb
        else:
            r.eligible_80tta_ttb = min(inp.savings_interest_80tta, self.LIMIT_80TTA)
            if r.eligible_80tta_ttb:
                r.breakdown["Savings Interest (Sec 80TTA)"] = r.eligible_80tta_ttb

        # ── Section 80U ────────────────────────────────────────────────────
        if inp.disability_80u > 0:
            r.eligible_80u = self.LIMIT_80U_SEVERE if inp.severe_disability_80u else self.LIMIT_80U_NORMAL
            r.breakdown["Own Disability (Sec 80U)"] = r.eligible_80u

        # ── Totals ─────────────────────────────────────────────────────────
        r.total_under_head = (r.standard_deduction + r.professional_tax_deduction +
                               r.hra_exemption + r.lta_exemption +
                               r.home_loan_interest_deduction)

        r.total_chapter_via = (r.total_80c_block + r.total_80d + r.eligible_80dd +
                                r.eligible_80ddb + r.eligible_80e + r.eligible_80ee +
                                r.eligible_80eea + r.eligible_80g + r.eligible_80gg +
                                r.eligible_80tta_ttb + r.eligible_80u)

        r.grand_total_deductions = r.total_under_head + r.total_chapter_via
        return r

    def _compute_new_regime(self, inp: DeductionInput, r: DeductionResult, gross_income: float) -> DeductionResult:
        """New regime: only standard deduction + 80CCD(2) allowed."""
        if inp.is_salaried:
            r.standard_deduction = self.STD_DEDUCTION_NEW   # Rs 75,000 for AY 2025-26
            r.breakdown["Standard Deduction (Sec 16) — New Regime"] = r.standard_deduction

        r.eligible_80ccd2 = inp.nps_employer_80ccd2
        if r.eligible_80ccd2:
            r.breakdown["NPS Employer Contribution (Sec 80CCD(2))"] = r.eligible_80ccd2

        r.total_under_head = r.standard_deduction
        r.total_chapter_via = r.eligible_80ccd2
        r.grand_total_deductions = r.total_under_head + r.total_chapter_via

        r.breakdown["NOTE"] = (
            "Under New Regime, most deductions u/s 80C, 80D, HRA, etc. "
            "are NOT available. Only Std. Deduction (₹75,000) & "
            "employer NPS contribution (Sec 80CCD(2)) are allowed."
        )
        return r

    def _compute_hra(self, inp: DeductionInput) -> float:
        """
        HRA Exemption = Minimum of:
        1. Actual HRA received
        2. Actual rent paid − 10% of Basic+DA
        3. 50% of Basic+DA (metro) / 40% (non-metro)
        """
        basic_da = inp.basic_da_for_hra
        actual_hra = inp.hra_received
        rent_paid = inp.rent_paid_actual

        metro_pct = 50 if inp.is_metro else 40
        exemption = min(
            actual_hra,
            rent_paid - (basic_da * 0.10),
            basic_da * metro_pct / 100,
        )
        return max(0, exemption)
