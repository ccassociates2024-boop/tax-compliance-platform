"""
TDS Compliance Engine — AY 2025-26
Covers:
  • 234E interest on late TDS filing
  • 234C-style TDS default interest (TRACES)
  • Challan matching — deductions vs challans
  • 26Q / 24Q data validation & preparation
  • Section 192 salary TDS computation
  • Common TDS sections & rates
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
from typing import Optional
import re


# ─── TDS RATE TABLE ───────────────────────────────────────────────────────────

TDS_SECTIONS = {
    "192":  {"description": "Salary",                          "rate_resident": None,  "threshold": 0},
    "192A": {"description": "EPF premature withdrawal",        "rate_resident": 10,    "threshold": 50_000},
    "193":  {"description": "Interest on Securities",          "rate_resident": 10,    "threshold": 10_000},
    "194":  {"description": "Dividend",                        "rate_resident": 10,    "threshold": 5_000},
    "194A": {"description": "Interest other than securities",  "rate_resident": 10,    "threshold": 40_000},
    "194B": {"description": "Lottery / Crossword",             "rate_resident": 30,    "threshold": 10_000},
    "194C": {"description": "Payments to Contractors",         "rate_resident": 1,     "threshold": 30_000,
             "rate_company": 2,  "annual_threshold": 100_000},
    "194D": {"description": "Insurance Commission",            "rate_resident": 5,     "threshold": 15_000},
    "194DA": {"description": "Maturity of Life Insurance",     "rate_resident": 5,     "threshold": 100_000},
    "194G": {"description": "Commission on Lottery",           "rate_resident": 5,     "threshold": 15_000},
    "194H": {"description": "Commission / Brokerage",          "rate_resident": 5,     "threshold": 15_000},
    "194I": {"description": "Rent",                            "rate_resident": 10,    "threshold": 240_000,
             "rate_plant": 2},
    "194IA": {"description": "Transfer of immovable property", "rate_resident": 1,     "threshold": 5_000_000},
    "194IB": {"description": "Rent by individual / HUF",      "rate_resident": 5,     "threshold": 50_000},
    "194IC": {"description": "Joint Development Agreement",    "rate_resident": 10,    "threshold": 0},
    "194J": {"description": "Professional / Technical Fees",   "rate_resident": 10,    "threshold": 30_000,
             "rate_technical": 2},
    "194K": {"description": "Income from MF units",            "rate_resident": 10,    "threshold": 5_000},
    "194LA": {"description": "Compensation on compulsory acq.", "rate_resident": 10,   "threshold": 250_000},
    "194LBA": {"description": "Business trust income",         "rate_resident": 10,    "threshold": 0},
    "194M": {"description": "Payment by individual/HUF >50L",  "rate_resident": 5,    "threshold": 5_000_000},
    "194N": {"description": "Cash withdrawal",                 "rate_resident": 2,     "threshold": 2_000_000},
    "194O": {"description": "TDS on e-Commerce",               "rate_resident": 1,     "threshold": 0},
    "194P": {"description": "Senior citizen (75+) — bank",     "rate_resident": None,  "threshold": 0},
    "194Q": {"description": "Purchase of goods",               "rate_resident": 0.1,   "threshold": 5_000_000},
    "194R": {"description": "Perquisite / benefit",            "rate_resident": 10,    "threshold": 20_000},
    "194S": {"description": "VDA / Crypto",                    "rate_resident": 1,     "threshold": 10_000},
    "195":  {"description": "NRI / Foreign payment",           "rate_resident": None,  "threshold": 0},
    "206C": {"description": "TCS — various",                   "rate_resident": None,  "threshold": 0},
}

# Due dates for TDS deposit (government deductors vs non-government)
# Non-government: 7th of following month (30 April for March)
# Government: same day / 7th

DUE_DATE_MAP = {
    1: date(2025, 2, 7),
    2: date(2025, 3, 7),
    3: date(2025, 4, 7),
    4: date(2025, 5, 7),
    5: date(2025, 6, 7),
    6: date(2025, 7, 7),
    7: date(2025, 8, 7),
    8: date(2025, 9, 7),
    9: date(2025, 10, 7),
    10: date(2025, 11, 7),
    11: date(2025, 12, 7),
    12: date(2026, 1, 7),   # March special: 30 April for non-govt
}
MARCH_DUE_DATE_NON_GOVT = date(2026, 4, 30)

# Return filing due dates (quarterly)
RETURN_DUE_DATES = {
    "Q1": {"period": "Apr–Jun 2024", "due": date(2024, 7, 31)},
    "Q2": {"period": "Jul–Sep 2024", "due": date(2024, 10, 31)},
    "Q3": {"period": "Oct–Dec 2024", "due": date(2025, 1, 31)},
    "Q4": {"period": "Jan–Mar 2025", "due": date(2025, 5, 31)},
}


# ─── DATA CLASSES ─────────────────────────────────────────────────────────────

@dataclass
class TDSDeduction:
    """A single TDS deduction entry (line in 26Q / 24Q)."""
    deductee_name: str
    deductee_pan: str
    section: str
    payment_date: date
    payment_amount: float
    tds_deducted: float
    tds_deposited: float = 0.0
    challan_number: str = ""
    challan_date: Optional[date] = None
    bsr_code: str = ""
    deductee_type: str = "resident"   # resident / company / nri
    remarks: str = ""


@dataclass
class TDSChallan:
    """A TDS challan (ITNS 281) deposit record."""
    challan_number: str
    bsr_code: str
    deposit_date: date
    amount: float
    section: str
    period_month: int   # 1-12
    period_year: int
    minor_head: str = "200"   # 200=TDS, 400=TDS on regular assessment
    nature_of_payment: str = ""
    matched: bool = False
    matched_deductions: list = field(default_factory=list)


@dataclass
class ChallanMatchResult:
    """Result of matching deductions to challans."""
    deduction: TDSDeduction
    matched_challan: Optional[TDSChallan]
    status: str          # matched / unmatched / short / excess
    short_amount: float = 0.0
    excess_amount: float = 0.0
    delay_days: int = 0
    interest_234C: float = 0.0   # Interest on late deposit
    remarks: str = ""


@dataclass
class Form234EResult:
    """Section 234E — late filing fee."""
    quarter: str
    return_type: str      # 26Q / 24Q / 27Q / 27EQ
    due_date: date
    actual_filing_date: Optional[date]
    delay_days: int
    fee_per_day: float = 200.0      # Rs 200/day
    total_fee: float = 0.0
    max_fee_cap: float = 0.0        # Capped at TDS amount
    applicable_fee: float = 0.0
    waiver_possible: bool = False


@dataclass
class TDSDefaultSummary:
    """Aggregated defaults — short deduction, late deposit, late filing."""
    total_tds_deductible: float = 0.0
    total_tds_deducted: float = 0.0
    total_tds_deposited: float = 0.0
    short_deduction: float = 0.0
    short_deposit: float = 0.0
    interest_on_short_deduction: float = 0.0   # 1% per month u/s 201(1A)
    interest_on_late_deposit: float = 0.0      # 1.5% per month u/s 201(1A)
    form_234e_fee: float = 0.0
    total_demand: float = 0.0
    challan_matches: list = field(default_factory=list)   # list[ChallanMatchResult]
    form_234e_results: list = field(default_factory=list) # list[Form234EResult]


@dataclass
class ReturnEntry26Q:
    """26Q — TDS on non-salary payments."""
    tan: str
    deductor_name: str
    quarter: str           # Q1/Q2/Q3/Q4
    financial_year: str
    deductions: list = field(default_factory=list)   # list[TDSDeduction]
    challans: list = field(default_factory=list)      # list[TDSChallan]


@dataclass
class ReturnEntry24Q:
    """24Q — TDS on salary (Form 16 source)."""
    tan: str
    deductor_name: str
    quarter: str
    financial_year: str
    employees: list = field(default_factory=list)     # list[TDSDeduction] with 192
    challans: list = field(default_factory=list)


# ─── ENGINE ───────────────────────────────────────────────────────────────────

class TDSEngine:
    """
    Main TDS compliance computation engine.
    """

    # ── 234E — Late Filing Fee ─────────────────────────────────────────────

    def compute_234e(
        self,
        quarter: str,
        return_type: str,
        actual_filing_date: Optional[date],
        total_tds_amount: float,
    ) -> Form234EResult:
        """
        Section 234E: ₹200/day from due date to filing date.
        Total fee capped at TDS amount in the return.
        """
        qdata = RETURN_DUE_DATES.get(quarter)
        if not qdata:
            raise ValueError(f"Invalid quarter: {quarter}. Use Q1/Q2/Q3/Q4.")

        due_date = qdata["due"]
        today = date.today()
        filing_date = actual_filing_date or today

        delay_days = max(0, (filing_date - due_date).days)
        fee_per_day = 200.0
        gross_fee = delay_days * fee_per_day
        cap = total_tds_amount   # Fee ≤ TDS amount
        applicable_fee = min(gross_fee, cap)

        return Form234EResult(
            quarter=quarter,
            return_type=return_type,
            due_date=due_date,
            actual_filing_date=filing_date,
            delay_days=delay_days,
            fee_per_day=fee_per_day,
            total_fee=gross_fee,
            max_fee_cap=cap,
            applicable_fee=applicable_fee,
            waiver_possible=(delay_days > 0 and applicable_fee == 0),
        )

    # ── Challan Matching ───────────────────────────────────────────────────

    def match_challans(
        self,
        deductions: list[TDSDeduction],
        challans: list[TDSChallan],
        is_government_deductor: bool = False,
    ) -> list[ChallanMatchResult]:
        """
        Match each deduction to a challan by BSR+challan number or date+section.
        Computes 234C-style late deposit interest (1.5% per month u/s 201(1A)).
        """
        results = []
        challan_pool = {c.challan_number: c for c in challans if c.challan_number}
        challan_remaining = {c.challan_number: c.amount for c in challans if c.challan_number}

        for ded in deductions:
            due_date = self._deposit_due_date(ded.payment_date, is_government_deductor)
            matched_challan = None
            status = "unmatched"
            short_amt = 0.0
            excess_amt = 0.0
            delay_days = 0
            interest = 0.0

            # Try matching by challan number first
            if ded.challan_number and ded.challan_number in challan_pool:
                ch = challan_pool[ded.challan_number]
                remaining = challan_remaining.get(ch.challan_number, 0)
                if remaining >= ded.tds_deposited:
                    challan_remaining[ch.challan_number] -= ded.tds_deposited
                    matched_challan = ch
                    status = "matched"
                else:
                    short_amt = ded.tds_deducted - remaining
                    status = "short"
                    matched_challan = ch
            else:
                short_amt = ded.tds_deducted - ded.tds_deposited
                if short_amt <= 0:
                    short_amt = 0.0
                    status = "unmatched"   # deposited but no challan linked
                else:
                    status = "unmatched"

            # Compute delay interest if deposit date is known
            deposit_date = ded.challan_date or (matched_challan.deposit_date if matched_challan else None)
            if deposit_date and deposit_date > due_date:
                delay_days = (deposit_date - due_date).days
                months = max(1, -(-delay_days // 30))   # Ceiling division
                interest = ded.tds_deducted * 0.015 * months
            elif not deposit_date and ded.tds_deposited < ded.tds_deducted:
                # Not deposited at all — compute up to today
                delay_days = max(0, (date.today() - due_date).days)
                months = max(1, -(-delay_days // 30))
                interest = (ded.tds_deducted - ded.tds_deposited) * 0.015 * months

            results.append(ChallanMatchResult(
                deduction=ded,
                matched_challan=matched_challan,
                status=status,
                short_amount=round(short_amt, 2),
                excess_amount=round(excess_amt, 2),
                delay_days=delay_days,
                interest_234C=round(interest, 2),
                remarks=self._match_remarks(status, short_amt, delay_days, interest),
            ))

        return results

    def _deposit_due_date(self, payment_date: date, is_govt: bool) -> date:
        """Get TDS deposit due date for a given payment month."""
        m = payment_date.month
        y = payment_date.year

        if m == 3:
            if is_govt:
                return date(y, 3, 31)
            return MARCH_DUE_DATE_NON_GOVT

        # Next month 7th
        next_m = m + 1 if m < 12 else 1
        next_y = y if m < 12 else y + 1
        return date(next_y, next_m, 7)

    def _match_remarks(self, status: str, short: float, delay_days: int, interest: float) -> str:
        parts = []
        if status == "matched":
            parts.append("Challan matched.")
        elif status == "short":
            parts.append(f"Short deposit: ₹{short:,.2f}.")
        elif status == "unmatched":
            parts.append("No challan linked.")
        if delay_days > 0:
            parts.append(f"Late by {delay_days} days. Interest: ₹{interest:,.2f}.")
        return " ".join(parts)

    # ── Aggregate Default Summary ──────────────────────────────────────────

    def compute_defaults(
        self,
        deductions: list[TDSDeduction],
        challans: list[TDSChallan],
        filing_date: Optional[date],
        quarter: str,
        return_type: str = "26Q",
        is_govt: bool = False,
    ) -> TDSDefaultSummary:
        s = TDSDefaultSummary()

        for d in deductions:
            rate_info = TDS_SECTIONS.get(d.section, {})
            rate = rate_info.get("rate_resident") or 0
            if rate:
                expected = d.payment_amount * rate / 100
                s.total_tds_deductible += expected
            s.total_tds_deducted += d.tds_deducted
            s.total_tds_deposited += d.tds_deposited

        s.short_deduction = max(0, s.total_tds_deductible - s.total_tds_deducted)
        s.short_deposit = max(0, s.total_tds_deducted - s.total_tds_deposited)

        # Interest on short deduction: 1% per month from date of deductibility
        if s.short_deduction > 0:
            months = 1   # Simplified; real computation needs per-transaction dates
            s.interest_on_short_deduction = s.short_deduction * 0.01 * months

        # Challan matching and late deposit interest
        matches = self.match_challans(deductions, challans, is_govt)
        s.challan_matches = matches
        s.interest_on_late_deposit = sum(m.interest_234C for m in matches)

        # 234E late filing fee
        fee_result = self.compute_234e(
            quarter, return_type, filing_date, s.total_tds_deducted
        )
        s.form_234e_results = [fee_result]
        s.form_234e_fee = fee_result.applicable_fee

        s.total_demand = (
            s.short_deduction +
            s.short_deposit +
            s.interest_on_short_deduction +
            s.interest_on_late_deposit +
            s.form_234e_fee
        )
        return s

    # ── TDS Rate Lookup ────────────────────────────────────────────────────

    def lookup_tds_rate(self, section: str, deductee_type: str = "resident",
                        payment_amount: float = 0) -> dict:
        info = TDS_SECTIONS.get(section.upper())
        if not info:
            return {"error": f"Section {section} not found in TDS rate table."}

        rate = info.get("rate_resident")
        if deductee_type == "company" and "rate_company" in info:
            rate = info["rate_company"]
        if "technical" in deductee_type.lower() and "rate_technical" in info:
            rate = info["rate_technical"]

        threshold = info.get("threshold", 0)
        annual_threshold = info.get("annual_threshold", threshold)

        tds_amount = None
        if rate and payment_amount > threshold:
            tds_amount = payment_amount * rate / 100

        return {
            "section": section,
            "description": info["description"],
            "rate_percent": rate,
            "threshold": threshold,
            "annual_threshold": annual_threshold,
            "payment_amount": payment_amount,
            "tds_deductible": round(tds_amount, 2) if tds_amount else None,
            "above_threshold": payment_amount > threshold if threshold else True,
            "note": "Rate may be lower if valid PAN not furnished (20% applies). DTAA may reduce NRI rate.",
        }

    # ── PAN Validation ────────────────────────────────────────────────────

    def validate_pan(self, pan: str) -> dict:
        """Validate PAN format: AAAAA1234A"""
        pan = pan.strip().upper()
        pattern = r'^[A-Z]{3}[ABCFGHLJPTK][A-Z]\d{4}[A-Z]$'
        valid = bool(re.match(pattern, pan))
        return {
            "pan": pan,
            "valid": valid,
            "entity_type": self._pan_entity_type(pan[3]) if valid else None,
            "error": None if valid else "Invalid PAN format. Expected: AAAAA1234A",
        }

    def _pan_entity_type(self, fourth_char: str) -> str:
        return {
            "P": "Individual",
            "C": "Company",
            "H": "HUF",
            "F": "Firm",
            "A": "AOP",
            "T": "Trust",
            "B": "BOI",
            "L": "Local Authority",
            "J": "Artificial Juridical Person",
            "G": "Government",
        }.get(fourth_char, "Unknown")

    # ── 26Q Data Validator ────────────────────────────────────────────────

    def validate_26q(self, entry: ReturnEntry26Q) -> dict:
        errors = []
        warnings = []

        if not re.match(r'^[A-Z]{4}\d{5}[A-Z]$', entry.tan.upper()):
            errors.append(f"Invalid TAN format: {entry.tan}")

        for i, ded in enumerate(entry.deductions):
            pan_check = self.validate_pan(ded.deductee_pan)
            if not pan_check["valid"]:
                if ded.deductee_pan in ("PANAPPLIED", "PANNOTAVBL", "PANINVALID"):
                    warnings.append(f"Row {i+1}: PAN placeholder used — TDS @ 20% applies.")
                else:
                    errors.append(f"Row {i+1}: {pan_check['error']} — PAN: {ded.deductee_pan}")

            if ded.section not in TDS_SECTIONS:
                errors.append(f"Row {i+1}: Unknown section {ded.section}")

            if ded.tds_deducted > ded.payment_amount:
                errors.append(f"Row {i+1}: TDS deducted ({ded.tds_deducted}) > payment amount ({ded.payment_amount})")

            if ded.tds_deducted > 0 and ded.tds_deposited == 0:
                warnings.append(f"Row {i+1}: TDS deducted but no deposit/challan linked for {ded.deductee_name}")

        total_deducted = sum(d.tds_deducted for d in entry.deductions)
        total_challan = sum(c.amount for c in entry.challans)
        if abs(total_deducted - total_challan) > 1.0:
            warnings.append(
                f"Deductions total ₹{total_deducted:,.2f} vs challan total ₹{total_challan:,.2f}. "
                "Difference: ₹{:.2f}.".format(abs(total_deducted - total_challan))
            )

        return {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "deductee_count": len(entry.deductions),
                "challan_count": len(entry.challans),
                "total_tds_deducted": round(total_deducted, 2),
                "total_challan_amount": round(total_challan, 2),
            },
        }


def get_tds_engine() -> TDSEngine:
    return TDSEngine()
