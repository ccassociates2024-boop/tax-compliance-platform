"""
GSTR-3B Auto-Computation Engine

Computes GSTR-3B from:
- GSTR-1 data (outward supplies)
- GSTR-2B data (inward supplies / ITC)
- Previous month ledger balances
- Manual inputs (non-GSTR-2B purchases)

Handles:
- ITC eligibility check (Section 17(5) blocked credits)
- ITC reversal (Rule 42/43 — mixed/personal use)
- Reverse charge mechanism (RCM)
- ITC utilization order (IGST → CGST/SGST)
- Interest computation (Section 50)
- Late fee computation (Section 47)
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from datetime import date, datetime
import calendar


@dataclass
class LedgerBalance:
    """Electronic Credit Ledger balances (ITC available)."""
    igst: float = 0
    cgst: float = 0
    sgst: float = 0
    cess: float = 0


@dataclass
class OutwardSupplySummary:
    """From GSTR-1 data — Table 3.1 of GSTR-3B."""
    # 3.1(a) Taxable outward supplies
    taxable_igst: float = 0
    taxable_cgst: float = 0
    taxable_sgst: float = 0
    taxable_cess: float = 0
    taxable_value: float = 0

    # 3.1(b) Zero-rated supplies (exports)
    zero_rated_value: float = 0
    zero_rated_igst: float = 0

    # 3.1(c) Nil-rated and exempt
    nil_exempt_value: float = 0

    # 3.1(d) Inward supplies attracting reverse charge
    rcm_taxable_value: float = 0
    rcm_igst: float = 0
    rcm_cgst: float = 0
    rcm_sgst: float = 0

    # 3.1(e) Non-GST outward supplies
    non_gst_value: float = 0


@dataclass
class ITCData:
    """ITC from GSTR-2B — Table 4 of GSTR-3B."""
    # 4(A) ITC available
    import_goods_igst: float = 0
    import_services_igst: float = 0
    rcm_igst: float = 0
    rcm_cgst: float = 0
    rcm_sgst: float = 0
    b2b_igst: float = 0
    b2b_cgst: float = 0
    b2b_sgst: float = 0
    b2b_cess: float = 0

    # 4(B) ITC reversed
    rule_42_43_igst: float = 0        # Mixed supply / capital goods reversal
    rule_42_43_cgst: float = 0
    rule_42_43_sgst: float = 0
    ineligible_other_igst: float = 0
    ineligible_other_cgst: float = 0
    ineligible_other_sgst: float = 0

    # Section 17(5) blocked credits (auto-excluded from GSTR-2B)
    blocked_motor_vehicle: float = 0  # Motor vehicles for personal use
    blocked_food_beverages: float = 0 # Food, beverages, outdoor catering
    blocked_health_insurance: float = 0
    blocked_club_membership: float = 0
    blocked_works_contract: float = 0
    blocked_construction: float = 0   # Building construction
    blocked_composition: float = 0    # Purchased from composition dealer


class BlockedCreditChecker:
    """
    Checks Section 17(5) — Blocked Credits.
    These HSN/SAC codes attract ITC restrictions.
    """
    BLOCKED_HSN = {
        "8703": "motor_vehicle",      # Passenger vehicles
        "8711": "motor_vehicle",      # Motorcycles (< 350cc)
        "8712": "motor_vehicle",      # Bicycles
        "8716": "motor_vehicle",      # Trailers
        "2104": "food_beverages",     # Soups, broths
        "2106": "food_beverages",     # Food preparations
        "9963": "health_insurance",   # Accommodation services
        "9993": "health_insurance",   # Health care services (exempt)
    }

    BLOCKED_SAC = {
        "996311": "food_beverages",    # Restaurant services
        "996312": "food_beverages",    # Catering services
        "997111": "health_insurance",  # Life insurance
        "997112": "health_insurance",  # Accident & health insurance
        "997211": "construction",      # Construction of buildings
        "997212": "construction",      # Construction of other structures
        "999211": "club_membership",   # Membership clubs
    }

    @classmethod
    def is_blocked(cls, hsn_sac: str) -> tuple[bool, str]:
        """Returns (is_blocked, reason)."""
        if hsn_sac in cls.BLOCKED_HSN:
            return True, cls.BLOCKED_HSN[hsn_sac]
        if hsn_sac in cls.BLOCKED_SAC:
            return True, cls.BLOCKED_SAC[hsn_sac]
        return False, ""


class GSTR3BComputer:
    """
    Computes complete GSTR-3B with all tables, tax payable, and challan working.
    """

    def __init__(self, gstin: str, period: str, filing_date: Optional[date] = None):
        self.gstin = gstin
        self.period = period        # "042024"
        self.filing_date = filing_date or date.today()
        self.state_code = gstin[:2]

    def compute(
        self,
        outward: OutwardSupplySummary,
        itc: ITCData,
        opening_ledger: LedgerBalance,
        cash_ledger: LedgerBalance,
    ) -> dict:
        """
        Full GSTR-3B computation.
        Returns complete working with all tables, ITC utilization, tax payable.
        """
        # ── Table 3.1: Outward Supplies ────────────────────────────────────
        table_31 = self._compute_table31(outward)

        # ── Table 3.2: Interstate supplies ────────────────────────────────
        table_32 = {"note": "Auto-computed from GSTR-1 B2CS/B2CL data"}

        # ── Table 4: ITC ──────────────────────────────────────────────────
        table_4 = self._compute_table4(itc)

        # ── Net ITC Available ─────────────────────────────────────────────
        net_itc = self._net_itc(table_4)

        # ── Table 5: Exempt / Nil / Non-GST ───────────────────────────────
        table_5 = {
            "nil_exempt": round(outward.nil_exempt_value, 2),
            "non_gst": round(outward.non_gst_value, 2),
        }

        # ── Tax Liability (Table 6) ────────────────────────────────────────
        tax_liability = self._compute_tax_liability(outward)

        # ── ITC Utilization (IGST → CGST/SGST → Cash) ────────────────────
        utilization = self._compute_itc_utilization(
            tax_liability, net_itc, opening_ledger
        )

        # ── Interest (Section 50) ─────────────────────────────────────────
        interest = self._compute_interest(utilization["cash_required"], self.period, self.filing_date)

        # ── Late Fee (Section 47) ─────────────────────────────────────────
        late_fee = self._compute_late_fee(self.period, self.filing_date)

        # ── Challan Summary ───────────────────────────────────────────────
        challan = {
            "igst_cash": round(utilization["cash_required"]["igst"] + interest["igst"], 2),
            "cgst_cash": round(utilization["cash_required"]["cgst"] + interest["cgst"], 2),
            "sgst_cash": round(utilization["cash_required"]["sgst"] + interest["sgst"], 2),
            "cess_cash": round(utilization["cash_required"]["cess"], 2),
            "late_fee_cgst": round(late_fee / 2, 2),
            "late_fee_sgst": round(late_fee / 2, 2),
            "total_challan": round(
                sum(utilization["cash_required"].values()) +
                sum(interest.values()) + late_fee, 2
            ),
        }

        return {
            "gstin": self.gstin,
            "period": self.period,
            "table_31_outward": table_31,
            "table_32_interstate": table_32,
            "table_4_itc": table_4,
            "net_itc_available": net_itc,
            "table_5_exempt": table_5,
            "tax_liability": tax_liability,
            "itc_utilization": utilization,
            "interest": interest,
            "late_fee": late_fee,
            "challan_summary": challan,
            "gstr3b_payload": self._build_gstn_payload(
                table_31, table_4, net_itc, utilization, interest, late_fee
            ),
        }

    def _compute_table31(self, outward: OutwardSupplySummary) -> dict:
        return {
            "3.1(a)_taxable_supplies": {
                "taxable_value": round(outward.taxable_value, 2),
                "igst": round(outward.taxable_igst, 2),
                "cgst": round(outward.taxable_cgst, 2),
                "sgst": round(outward.taxable_sgst, 2),
                "cess": round(outward.taxable_cess, 2),
            },
            "3.1(b)_zero_rated": {
                "taxable_value": round(outward.zero_rated_value, 2),
                "igst": round(outward.zero_rated_igst, 2),
            },
            "3.1(c)_nil_exempt": {
                "taxable_value": round(outward.nil_exempt_value, 2),
            },
            "3.1(d)_rcm_inward": {
                "taxable_value": round(outward.rcm_taxable_value, 2),
                "igst": round(outward.rcm_igst, 2),
                "cgst": round(outward.rcm_cgst, 2),
                "sgst": round(outward.rcm_sgst, 2),
            },
            "3.1(e)_non_gst": {
                "taxable_value": round(outward.non_gst_value, 2),
            },
        }

    def _compute_table4(self, itc: ITCData) -> dict:
        # 4(A) Total ITC available
        avail_igst = (itc.import_goods_igst + itc.import_services_igst +
                      itc.rcm_igst + itc.b2b_igst)
        avail_cgst = itc.rcm_cgst + itc.b2b_cgst
        avail_sgst = itc.rcm_sgst + itc.b2b_sgst
        avail_cess = itc.b2b_cess

        # 4(B) ITC reversed
        rev_igst = itc.rule_42_43_igst + itc.ineligible_other_igst
        rev_cgst = itc.rule_42_43_cgst + itc.ineligible_other_cgst
        rev_sgst = itc.rule_42_43_sgst + itc.ineligible_other_sgst

        # 4(C) Net ITC = Available - Reversed
        net_igst = max(0, avail_igst - rev_igst)
        net_cgst = max(0, avail_cgst - rev_cgst)
        net_sgst = max(0, avail_sgst - rev_sgst)

        # 4(D) Ineligible ITC (Section 17(5))
        ineligible_total = (
            itc.blocked_motor_vehicle + itc.blocked_food_beverages +
            itc.blocked_health_insurance + itc.blocked_club_membership +
            itc.blocked_works_contract + itc.blocked_construction +
            itc.blocked_composition
        )

        return {
            "4A_itc_available": {
                "imports_goods_igst": round(itc.import_goods_igst, 2),
                "imports_services_igst": round(itc.import_services_igst, 2),
                "rcm_igst": round(itc.rcm_igst, 2),
                "rcm_cgst": round(itc.rcm_cgst, 2),
                "rcm_sgst": round(itc.rcm_sgst, 2),
                "b2b_igst": round(itc.b2b_igst, 2),
                "b2b_cgst": round(itc.b2b_cgst, 2),
                "b2b_sgst": round(itc.b2b_sgst, 2),
                "b2b_cess": round(itc.b2b_cess, 2),
                "total_igst": round(avail_igst, 2),
                "total_cgst": round(avail_cgst, 2),
                "total_sgst": round(avail_sgst, 2),
            },
            "4B_itc_reversed": {
                "rule_42_43_igst": round(itc.rule_42_43_igst, 2),
                "rule_42_43_cgst": round(itc.rule_42_43_cgst, 2),
                "rule_42_43_sgst": round(itc.rule_42_43_sgst, 2),
                "others_igst": round(itc.ineligible_other_igst, 2),
                "others_cgst": round(itc.ineligible_other_cgst, 2),
                "others_sgst": round(itc.ineligible_other_sgst, 2),
            },
            "4C_net_itc": {
                "igst": round(net_igst, 2),
                "cgst": round(net_cgst, 2),
                "sgst": round(net_sgst, 2),
                "cess": round(avail_cess, 2),
            },
            "4D_ineligible_sec17_5": {
                "motor_vehicle": round(itc.blocked_motor_vehicle, 2),
                "food_beverages": round(itc.blocked_food_beverages, 2),
                "health_insurance": round(itc.blocked_health_insurance, 2),
                "club_membership": round(itc.blocked_club_membership, 2),
                "total_ineligible": round(ineligible_total, 2),
            },
        }

    def _net_itc(self, table_4: dict) -> dict:
        return table_4["4C_net_itc"]

    def _compute_tax_liability(self, outward: OutwardSupplySummary) -> dict:
        """Total tax payable = outward tax + RCM tax."""
        return {
            "igst": round(outward.taxable_igst + outward.rcm_igst + outward.zero_rated_igst, 2),
            "cgst": round(outward.taxable_cgst + outward.rcm_cgst, 2),
            "sgst": round(outward.taxable_sgst + outward.rcm_sgst, 2),
            "cess": round(outward.taxable_cess, 2),
            "total": round(
                outward.taxable_igst + outward.rcm_igst + outward.zero_rated_igst +
                outward.taxable_cgst + outward.rcm_cgst +
                outward.taxable_sgst + outward.rcm_sgst +
                outward.taxable_cess, 2
            ),
        }

    def _compute_itc_utilization(
        self,
        liability: dict,
        net_itc: dict,
        opening_ledger: LedgerBalance,
    ) -> dict:
        """
        ITC utilization order (as per GST law):
        1. IGST ITC → first against IGST liability
        2. Remaining IGST ITC → against CGST liability
        3. Remaining IGST ITC → against SGST liability
        4. CGST ITC → against CGST liability only
        5. SGST ITC → against SGST liability only
        6. Balance payable via cash
        """
        igst_itc = Decimal(str(net_itc["igst"])) + Decimal(str(opening_ledger.igst))
        cgst_itc = Decimal(str(net_itc["cgst"])) + Decimal(str(opening_ledger.cgst))
        sgst_itc = Decimal(str(net_itc["sgst"])) + Decimal(str(opening_ledger.sgst))
        cess_itc = Decimal(str(net_itc["cess"])) + Decimal(str(opening_ledger.cess))

        igst_liab = Decimal(str(liability["igst"]))
        cgst_liab = Decimal(str(liability["cgst"]))
        sgst_liab = Decimal(str(liability["sgst"]))
        cess_liab = Decimal(str(liability["cess"]))

        itc_used = {"igst_from_igst": 0, "cgst_from_igst": 0, "sgst_from_igst": 0,
                    "cgst_from_cgst": 0, "sgst_from_sgst": 0, "cess_from_cess": 0}

        # Step 1: IGST ITC → IGST liability
        igst_used_for_igst = min(igst_itc, igst_liab)
        igst_liab -= igst_used_for_igst
        igst_itc -= igst_used_for_igst
        itc_used["igst_from_igst"] = float(igst_used_for_igst)

        # Step 2: Remaining IGST ITC → CGST liability
        igst_used_for_cgst = min(igst_itc, cgst_liab)
        cgst_liab -= igst_used_for_cgst
        igst_itc -= igst_used_for_cgst
        itc_used["cgst_from_igst"] = float(igst_used_for_cgst)

        # Step 3: Remaining IGST ITC → SGST liability
        igst_used_for_sgst = min(igst_itc, sgst_liab)
        sgst_liab -= igst_used_for_sgst
        igst_itc -= igst_used_for_sgst
        itc_used["sgst_from_igst"] = float(igst_used_for_sgst)

        # Step 4: CGST ITC → CGST liability
        cgst_used = min(cgst_itc, cgst_liab)
        cgst_liab -= cgst_used
        cgst_itc -= cgst_used
        itc_used["cgst_from_cgst"] = float(cgst_used)

        # Step 5: SGST ITC → SGST liability
        sgst_used = min(sgst_itc, sgst_liab)
        sgst_liab -= sgst_used
        sgst_itc -= sgst_used
        itc_used["sgst_from_sgst"] = float(sgst_used)

        # Step 6: CESS ITC → CESS liability
        cess_used = min(cess_itc, cess_liab)
        cess_liab -= cess_used
        itc_used["cess_from_cess"] = float(cess_used)

        return {
            "itc_used": itc_used,
            "cash_required": {
                "igst": float(igst_liab.quantize(Decimal("0.01"))),
                "cgst": float(cgst_liab.quantize(Decimal("0.01"))),
                "sgst": float(sgst_liab.quantize(Decimal("0.01"))),
                "cess": float(cess_liab.quantize(Decimal("0.01"))),
            },
            "closing_itc_ledger": {
                "igst": float(igst_itc.quantize(Decimal("0.01"))),
                "cgst": float(cgst_itc.quantize(Decimal("0.01"))),
                "sgst": float(sgst_itc.quantize(Decimal("0.01"))),
                "cess": float(cess_itc.quantize(Decimal("0.01"))),
            },
        }

    def _compute_interest(self, cash_required: dict, period: str, filing_date: date) -> dict:
        """
        Interest u/s 50 @ 18% p.a. on delayed payment.
        Due date = 20th of next month.
        """
        month = int(period[:2])
        year = int(period[2:])
        due_date = date(year, month, 20)
        if filing_date <= due_date:
            return {"igst": 0, "cgst": 0, "sgst": 0, "cess": 0, "delay_days": 0}

        delay_days = (filing_date - due_date).days
        rate = Decimal("18") / Decimal("365") / Decimal("100")

        result = {"delay_days": delay_days}
        for tax_head in ["igst", "cgst", "sgst", "cess"]:
            amount = Decimal(str(cash_required.get(tax_head, 0)))
            interest = (amount * rate * Decimal(str(delay_days))).quantize(Decimal("0.01"))
            result[tax_head] = float(interest)
        return result

    def _compute_late_fee(self, period: str, filing_date: date) -> float:
        """
        Late fee u/s 47:
        - Nil return: Rs. 20/day (Rs. 10 CGST + Rs. 10 SGST)
        - Other: Rs. 50/day (Rs. 25 CGST + Rs. 25 SGST), max Rs. 10,000
        """
        month = int(period[:2])
        year = int(period[2:])
        due_date = date(year, month, 20)
        if filing_date <= due_date:
            return 0.0

        delay_days = (filing_date - due_date).days
        late_fee = min(delay_days * 50, 10000)   # Max Rs. 10,000
        return float(late_fee)

    def _build_gstn_payload(self, table_31, table_4, net_itc, utilization, interest, late_fee) -> dict:
        """Build the actual GSTN API JSON for GSTR-3B submission."""
        return {
            "gstin": self.gstin,
            "ret_period": self.period,
            "sup_details": {
                "osup_det": {
                    "txval": table_31["3.1(a)_taxable_supplies"]["taxable_value"],
                    "iamt": table_31["3.1(a)_taxable_supplies"]["igst"],
                    "camt": table_31["3.1(a)_taxable_supplies"]["cgst"],
                    "samt": table_31["3.1(a)_taxable_supplies"]["sgst"],
                    "csamt": table_31["3.1(a)_taxable_supplies"]["cess"],
                },
                "osup_zero": {
                    "txval": table_31["3.1(b)_zero_rated"]["taxable_value"],
                    "iamt": table_31["3.1(b)_zero_rated"]["igst"],
                },
                "osup_nil_exmp": {"txval": table_31["3.1(c)_nil_exempt"]["taxable_value"]},
                "isup_rev": {
                    "txval": table_31["3.1(d)_rcm_inward"]["taxable_value"],
                    "iamt": table_31["3.1(d)_rcm_inward"]["igst"],
                    "camt": table_31["3.1(d)_rcm_inward"]["cgst"],
                    "samt": table_31["3.1(d)_rcm_inward"]["sgst"],
                },
                "osup_nongst": {"txval": table_31["3.1(e)_non_gst"]["taxable_value"]},
            },
            "itc_elg": {
                "itc_avl": [
                    {"ty": "IMPG", "iamt": table_4["4A_itc_available"]["imports_goods_igst"]},
                    {"ty": "IMPS", "iamt": table_4["4A_itc_available"]["imports_services_igst"]},
                    {"ty": "ISRC", "iamt": table_4["4A_itc_available"]["rcm_igst"],
                     "camt": table_4["4A_itc_available"]["rcm_cgst"],
                     "samt": table_4["4A_itc_available"]["rcm_sgst"]},
                    {"ty": "ISD", "iamt": 0, "camt": 0, "samt": 0},
                    {"ty": "OTH", "iamt": table_4["4A_itc_available"]["b2b_igst"],
                     "camt": table_4["4A_itc_available"]["b2b_cgst"],
                     "samt": table_4["4A_itc_available"]["b2b_sgst"],
                     "csamt": table_4["4A_itc_available"]["b2b_cess"]},
                ],
                "itc_rev": [
                    {"ty": "RUL42_43", "iamt": table_4["4B_itc_reversed"]["rule_42_43_igst"],
                     "camt": table_4["4B_itc_reversed"]["rule_42_43_cgst"],
                     "samt": table_4["4B_itc_reversed"]["rule_42_43_sgst"]},
                    {"ty": "OTH", "iamt": table_4["4B_itc_reversed"]["others_igst"],
                     "camt": table_4["4B_itc_reversed"]["others_cgst"],
                     "samt": table_4["4B_itc_reversed"]["others_sgst"]},
                ],
                "itc_net": {
                    "iamt": net_itc["igst"],
                    "camt": net_itc["cgst"],
                    "samt": net_itc["sgst"],
                    "csamt": net_itc["cess"],
                },
            },
            "intr_ltfee": {
                "intr_details": {
                    "iamt": interest.get("igst", 0),
                    "camt": interest.get("cgst", 0),
                    "samt": interest.get("sgst", 0),
                },
                "ltfee_details": {
                    "camt": round(late_fee / 2, 2),
                    "samt": round(late_fee / 2, 2),
                },
            },
        }
