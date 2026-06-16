"""
Pre-computed demo data — realistic Maharashtra CA practice scenario.
All amounts in paise (for consistency) or ₹ as noted in comments.
"""
from __future__ import annotations
import re
from typing import Any

# ─── DEMO CLIENTS ──────────────────────────────────────────────────────────────

DEMO_CLIENTS: list[dict] = [
    {
        "full_name": "Rajesh Deshmukh",
        "pan": "ABCPD1234R",
        "client_type": "individual",
        "email": "rajesh.deshmukh@gmail.com",
        "phone": "9876543210",
        "dob": "1985-06-15",
        "state_code": "27",
        "gst_registered": False,
        "is_tds_deductor": False,
        "current_fy": "2024-25",
        "tags": ["salaried", "itr-1"],
        "internal_notes": "Salaried employee at Infosys Pune. Home loan from SBI.",
    },
    {
        "full_name": "Sunita Joshi",
        "pan": "BFXPJ5678S",
        "client_type": "individual",
        "email": "sunita.joshi@designhub.in",
        "phone": "9123456780",
        "dob": "1979-11-22",
        "state_code": "27",
        "gstin": "27BFXPJ5678S1Z5",
        "gst_registered": True,
        "composition_scheme": False,
        "is_tds_deductor": False,
        "current_fy": "2024-25",
        "tags": ["freelancer", "gst", "itr-4"],
        "internal_notes": "Graphic designer / consultant in Nagpur. Presumptive 44ADA. GST on services.",
    },
    {
        "full_name": "Sahyadri Software Solutions Pvt Ltd",
        "pan": "AADCS3456M",
        "client_type": "company",
        "email": "accounts@sahyadrisoft.in",
        "phone": "9988776655",
        "dob": None,
        "state_code": "27",
        "gstin": "27AADCS3456M1Z2",
        "gst_registered": True,
        "tan": "PNES12345A",
        "is_tds_deductor": True,
        "current_fy": "2024-25",
        "tags": ["company", "tds-deductor", "gst", "itr-6"],
        "internal_notes": "Software startup, Pune. Pays salary + professional fees. TAN PNES12345A.",
    },
    {
        "full_name": "Vikram Patil",
        "pan": "CLHPP7890V",
        "client_type": "individual",
        "email": "vikram.patil@gmail.com",
        "phone": "9090909090",
        "dob": "1972-03-05",
        "state_code": "27",
        "gst_registered": False,
        "is_tds_deductor": False,
        "current_fy": "2024-25",
        "tags": ["business", "capital-gains", "itr-3"],
        "internal_notes": "Hardware trader in Nashik + sold equity MFs with LTCG. ITR-3 needed.",
    },
    {
        "full_name": "Pushpa Kulkarni",
        "pan": "DFZPK2345P",
        "client_type": "individual",
        "email": "pushpa.kulkarni@yahoo.in",
        "phone": "9966554433",
        "dob": "1953-09-01",
        "state_code": "27",
        "gst_registered": False,
        "is_tds_deductor": False,
        "current_fy": "2024-25",
        "tags": ["senior-citizen", "pension", "itr-1"],
        "internal_notes": "Retired govt employee, Thane. Pension + FD interest. 80TTB applicable.",
    },
]

# ─── MOCK ITR RESULTS ─────────────────────────────────────────────────────────

_ITR_RESULTS: dict[str, dict] = {
    "ABCPD1234R": {  # Rajesh Deshmukh — salaried
        "client_name": "Rajesh Deshmukh",
        "pan": "ABCPD1234R",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "itr_form": "ITR-1",
        "itr_form_reason": "Salaried individual with income up to ₹50 lakh. No capital gains or multiple house properties.",
        "income_summary": {
            "gross_salary": 1200000,
            "standard_deduction": 75000,
            "net_salary": 1125000,
            "house_property": -142000,
            "hp_set_off_restricted": False,
            "other_sources": 36000,
            "total_gross_income": 1019000,
        },
        "deductions_80": {
            "80C": 100000,
            "80D_self": 25000,
            "80D_parents": 0,
            "80TTA": 0,
            "total": 125000,
        },
        "regime_comparison": {
            "old": {
                "total_income_after_deductions": 894000,
                "tax_before_cess": 86700,
                "surcharge": 0,
                "health_education_cess": 3468,
                "rebate_87a": 0,
                "total_tax": 90168,
                "tds_credit": 72000,
                "advance_tax_paid": 0,
                "balance_tax_payable": 18168,
            },
            "new": {
                "total_income_after_deductions": 1044000,
                "standard_deduction_115bac": 75000,
                "taxable_income": 969000,
                "tax_before_cess": 110200,
                "surcharge": 0,
                "health_education_cess": 4408,
                "rebate_87a": 0,
                "total_tax": 114608,
                "tds_credit": 72000,
                "advance_tax_paid": 0,
                "balance_tax_payable": 42608,
            },
            "recommended": "old",
            "savings_in_old": 24440,
            "savings_in_old_pct": 21.3,
        },
        "advance_tax_schedule": [
            {"quarter": "Q1", "due_date": "15-Jun-2024", "cumulative_pct": 15, "amount": 13525},
            {"quarter": "Q2", "due_date": "15-Sep-2024", "cumulative_pct": 45, "amount": 40575},
            {"quarter": "Q3", "due_date": "15-Dec-2024", "cumulative_pct": 75, "amount": 67626},
            {"quarter": "Q4", "due_date": "15-Mar-2025", "cumulative_pct": 100, "amount": 90168},
        ],
        "deduction_optimizer_tips": [
            {
                "section": "80C",
                "current": 100000,
                "max": 150000,
                "gap": 50000,
                "tip": "You have ₹50,000 unused 80C room. Invest in ELSS, PPF or NPS to save ₹15,000 in tax.",
                "potential_saving": 15000,
            },
            {
                "section": "80D — Parents",
                "current": 0,
                "max": 50000,
                "gap": 50000,
                "tip": "No parents' health insurance claimed. If parents are senior citizens, you can claim ₹50,000 deduction u/s 80D — saving ₹15,450 in tax.",
                "potential_saving": 15450,
            },
        ],
        "form_26as_summary": {
            "total_tds_in_26as": 72000,
            "tds_on_salary": 72000,
            "tds_on_interest": 0,
            "mismatch_with_slips": False,
            "advance_tax_in_26as": 0,
        },
    },

    "BFXPJ5678S": {  # Sunita Joshi — freelancer
        "client_name": "Sunita Joshi",
        "pan": "BFXPJ5678S",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "itr_form": "ITR-4",
        "itr_form_reason": "Presumptive taxation u/s 44ADA — professional income. ITR-4 (Sugam) applies.",
        "income_summary": {
            "professional_receipts": 2800000,
            "presumptive_income_44ADA": 1400000,
            "other_sources": 0,
            "total_gross_income": 1400000,
        },
        "deductions_80": {
            "80C": 150000,
            "80D_self": 25000,
            "80CCD_1B_NPS": 50000,
            "total": 225000,
        },
        "regime_comparison": {
            "old": {
                "total_income_after_deductions": 1175000,
                "tax_before_cess": 218500,
                "surcharge": 0,
                "health_education_cess": 8740,
                "rebate_87a": 0,
                "total_tax": 227240,
                "tds_credit": 56000,
                "advance_tax_paid": 150000,
                "balance_tax_payable": 21240,
            },
            "new": {
                "total_income_after_deductions": 1325000,
                "standard_deduction_115bac": 75000,
                "taxable_income": 1325000,
                "tax_before_cess": 242500,
                "surcharge": 0,
                "health_education_cess": 9700,
                "rebate_87a": 0,
                "total_tax": 252200,
                "tds_credit": 56000,
                "advance_tax_paid": 150000,
                "balance_tax_payable": 46200,
            },
            "recommended": "old",
            "savings_in_old": 24960,
            "savings_in_old_pct": 9.9,
        },
        "advance_tax_schedule": [
            {"quarter": "Q1", "due_date": "15-Jun-2024", "cumulative_pct": 15, "amount": 34086},
            {"quarter": "Q2", "due_date": "15-Sep-2024", "cumulative_pct": 45, "amount": 102258},
            {"quarter": "Q3", "due_date": "15-Dec-2024", "cumulative_pct": 75, "amount": 170430},
            {"quarter": "Q4", "due_date": "15-Mar-2025", "cumulative_pct": 100, "amount": 227240},
        ],
        "deduction_optimizer_tips": [
            {
                "section": "80CCD(1B) — NPS",
                "current": 50000,
                "max": 50000,
                "gap": 0,
                "tip": "NPS deduction fully utilised. Well done!",
                "potential_saving": 0,
            }
        ],
        "gst_summary": {
            "gstin": "27BFXPJ5678S1Z5",
            "gstr2b_itc_available": 42000,
            "itc_in_books": 54000,
            "mismatch_amount": 12000,
            "mismatch_invoices": 3,
            "mismatch_detail": "3 purchase invoices (₹12,000 ITC) from Canva India and Adobe not filed in GSTR-1 by supplier. Do NOT claim until supplier files.",
            "gstr3b_output_tax": 252000,
            "gstr3b_itc_claimed": 42000,
            "net_gst_payable": 210000,
        },
    },

    "AADCS3456M": {  # Sahyadri Software Solutions — company, TDS deductor
        "client_name": "Sahyadri Software Solutions Pvt Ltd",
        "pan": "AADCS3456M",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "itr_form": "ITR-6",
        "itr_form_reason": "Domestic company not claiming exemption u/s 11. ITR-6 mandatory.",
        "tds_summary": {
            "tan": "PNES12345A",
            "quarters_filed": ["Q1", "Q2", "Q3"],
            "quarters_pending": ["Q4"],
            "deductions": [
                {
                    "section": "192",
                    "deductee": "Employees",
                    "gross_amount": 8400000,
                    "tds_amount": 756000,
                    "rate_pct": 9.0,
                    "challan_matched": True,
                },
                {
                    "section": "194J",
                    "deductee": "IT Consultants",
                    "gross_amount": 500000,
                    "tds_amount": 50000,
                    "rate_pct": 10.0,
                    "challan_matched": True,
                },
                {
                    "section": "194C",
                    "deductee": "Office Contractors",
                    "gross_amount": 240000,
                    "tds_amount": 4800,
                    "rate_pct": 2.0,
                    "challan_matched": False,
                    "challan_issue": "Challan ITNS281/Q3 not matched — BSR code mismatch. Please verify with bank.",
                },
            ],
            "234e_penalties": [
                {
                    "quarter": "Q2 FY 2024-25",
                    "return_type": "26Q",
                    "due_date": "31-Oct-2024",
                    "filed_date": "05-Nov-2024",
                    "delay_days": 5,
                    "tds_amount_in_return": 50000,
                    "gross_fee": 1000,
                    "applicable_fee": 1000,
                    "note": "₹200/day × 5 days = ₹1,000. Already deposited as ITNS 281.",
                }
            ],
        },
        "gst_summary": {
            "gstin": "27AADCS3456M1Z2",
            "turnover": 24000000,
            "gstr1_filed_periods": ["Apr-Sep 2024", "Oct-Dec 2024"],
            "gstr3b_filed_periods": ["Apr-Sep 2024", "Oct-Dec 2024"],
            "pending_periods": ["Jan-Mar 2025"],
            "itc_available_2b": 420000,
            "itc_claimed_3b": 420000,
            "reconciliation_status": "Clean",
        },
    },

    "CLHPP7890V": {  # Vikram Patil — business + capital gains
        "client_name": "Vikram Patil",
        "pan": "CLHPP7890V",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "itr_form": "ITR-3",
        "itr_form_reason": "Business income + Long Term Capital Gains on equity. ITR-3 required.",
        "income_summary": {
            "business_income_regular": 800000,
            "ltcg_112A_units_sold": 350000,
            "ltcg_112A_cost": 120000,
            "ltcg_112A_gain": 230000,
            "ltcg_exempt_1L": 100000,
            "ltcg_taxable": 130000,
            "other_sources": 22000,
            "total_gross_income": 822000,
        },
        "deductions_80": {
            "80C": 150000,
            "80D_self": 25000,
            "total": 175000,
        },
        "regime_comparison": {
            "old": {
                "slab_income_taxable": 647000,
                "slab_tax": 39900,
                "ltcg_tax_10pct": 13000,
                "surcharge": 0,
                "health_education_cess": 2116,
                "rebate_87a": 0,
                "total_tax": 55016,
                "tds_credit": 22000,
                "advance_tax_paid": 20000,
                "balance_tax_payable": 13016,
            },
            "new": {
                "slab_income_taxable": 822000,
                "standard_deduction_115bac": 75000,
                "taxable_income": 747000,
                "slab_tax": 62350,
                "ltcg_tax_10pct": 13000,
                "surcharge": 0,
                "health_education_cess": 3014,
                "rebate_87a": 0,
                "total_tax": 78364,
                "tds_credit": 22000,
                "advance_tax_paid": 20000,
                "balance_tax_payable": 36364,
            },
            "recommended": "old",
            "savings_in_old": 23348,
            "savings_in_old_pct": 29.8,
        },
        "tds_summary": {
            "234e_penalties": [
                {
                    "quarter": "Q4 FY 2023-24",
                    "return_type": "26Q",
                    "due_date": "31-May-2024",
                    "filed_date": "04-Jun-2024",
                    "delay_days": 4,
                    "tds_amount_in_return": 18000,
                    "gross_fee": 800,
                    "applicable_fee": 800,
                    "note": "₹200/day × 4 days = ₹800. Pay via Challan ITNS 281.",
                }
            ]
        },
    },

    "DFZPK2345P": {  # Pushpa Kulkarni — senior citizen
        "client_name": "Pushpa Kulkarni",
        "pan": "DFZPK2345P",
        "financial_year": "2024-25",
        "assessment_year": "2025-26",
        "itr_form": "ITR-1",
        "itr_form_reason": "Salaried/pension income up to ₹50 lakh. Senior citizen. ITR-1 (Sahaj).",
        "income_summary": {
            "pension": 600000,
            "standard_deduction": 50000,
            "net_salary_pension": 550000,
            "fd_interest": 120000,
            "other_sources": 120000,
            "total_gross_income": 670000,
        },
        "deductions_80": {
            "80TTB_senior_fd": 50000,
            "80D_self_senior": 50000,
            "80C": 100000,
            "total": 200000,
        },
        "regime_comparison": {
            "old": {
                "total_income_after_deductions": 470000,
                "tax_before_cess": 2000,
                "surcharge": 0,
                "health_education_cess": 80,
                "rebate_87a": 2080,
                "total_tax": 0,
                "tds_credit": 12000,
                "advance_tax_paid": 0,
                "refund_due": 12000,
                "note": "Rebate u/s 87A fully wipes out tax. TDS of ₹12,000 deducted on FD is fully refundable.",
            },
            "new": {
                "total_income_after_deductions": 670000,
                "standard_deduction_115bac": 75000,
                "taxable_income": 595000,
                "tax_before_cess": 17250,
                "surcharge": 0,
                "health_education_cess": 690,
                "rebate_87a": 0,
                "total_tax": 17940,
                "tds_credit": 12000,
                "balance_tax_payable": 5940,
            },
            "recommended": "old",
            "savings_in_old": 17940,
            "savings_in_old_pct": 100.0,
        },
        "advance_tax_schedule": [],
        "advance_tax_note": "No advance tax applicable — tax liability is fully covered by TDS on FD and is within exemption.",
        "deduction_optimizer_tips": [
            {
                "section": "80D — Senior Citizen",
                "current": 50000,
                "max": 50000,
                "gap": 0,
                "tip": "Maximum senior citizen health insurance deduction already claimed. ✓",
                "potential_saving": 0,
            }
        ],
        "form_26as_summary": {
            "total_tds_in_26as": 12000,
            "tds_on_salary": 0,
            "tds_on_interest": 12000,
            "mismatch_with_slips": False,
            "advance_tax_in_26as": 0,
            "refund_expected": 12000,
        },
    },
}


def get_mock_itr_result(pan: str) -> dict | None:
    return _ITR_RESULTS.get(pan.upper())


# ─── MOCK GST RESULTS ─────────────────────────────────────────────────────────

def get_mock_gst_result(pan: str) -> dict | None:
    data = _ITR_RESULTS.get(pan.upper(), {})
    gst = data.get("gst_summary")
    if not gst:
        return None
    return {
        "pan": pan.upper(),
        "client_name": data.get("client_name"),
        **gst,
        "gstr2b_mock": True,
        "note": "DEMO MODE: This data is simulated. In production, GSTR-2B is fetched live from GST portal.",
    }


# ─── MOCK TDS RESULTS ─────────────────────────────────────────────────────────

def get_mock_tds_result(pan: str) -> dict | None:
    data = _ITR_RESULTS.get(pan.upper(), {})
    tds = data.get("tds_summary")
    if not tds:
        return {
            "pan": pan.upper(),
            "client_name": data.get("client_name"),
            "message": "No TDS deductor activity for this client.",
            "is_tds_deductor": False,
        }
    return {
        "pan": pan.upper(),
        "client_name": data.get("client_name"),
        **tds,
        "traces_mock": True,
        "note": "DEMO MODE: This data is simulated. In production, data is fetched live from TRACES.",
    }


# ─── MOCK AI RESPONSES ────────────────────────────────────────────────────────

_AI_RULES: list[tuple[list[str], str]] = [
    (
        ["regime", "old.*new", "new.*old", "which.*save", "save.*tax", "better.*regime"],
        """**Old Regime vs New Regime Analysis** 🔍

For **Rajesh Deshmukh** (ABCPD1234R) based on demo data:

| | Old Regime | New Regime |
|---|---|---|
| Taxable Income | ₹8,94,000 | ₹9,69,000 |
| Total Tax | **₹90,168** | ₹1,14,608 |
| Balance Payable | ₹18,168 | ₹42,608 |

✅ **Old Regime saves ₹24,440 this year** because:
- Home loan interest deduction (₹1,42,000) is only available in old regime
- 80C investments (₹1,00,000) give relief only in old regime
- Medical insurance (₹25,000) is deductible only in old regime

**Recommendation:** Stick with **Old Regime** for AY 2025-26.""",
    ),
    (
        ["26as", "form 26", "tds mismatch", "mismatch", "salary.*tds", "tds.*salary"],
        """**Form 26AS Analysis** 📋

For the loaded demo client:

- **Form 26AS shows:** ₹72,000 TDS (Employer — Infosys Pune, BSR 0561234)
- **Salary slips show:** ₹72,000 TDS

✅ **No mismatch detected** — 26AS and salary slips are in agreement.

> Common mismatches happen when:
> - Employer files TDS return late (Q4 often delayed)
> - Employee changes job mid-year (previous employer's TDS may take 60 days to reflect)
> - Name/PAN mismatch in employer's records
>
> If you see a mismatch, first check TRACES under "View 26AS" and compare challan-wise.""",
    ),
    (
        ["deduction", "saving", "80c", "80d", "hra", "missing.*deduction", "save more"],
        """**Deduction Optimizer Report** 💰

For **Rajesh Deshmukh**, here are the gaps I found:

| Section | Invested | Limit | Gap | Tax Saving |
|---|---|---|---|---|
| 80C | ₹1,00,000 | ₹1,50,000 | **₹50,000** | **₹15,000** |
| 80D (Parents) | ₹0 | ₹50,000 | **₹50,000** | **₹15,450** |
| 80CCD(1B) NPS | ₹0 | ₹50,000 | **₹50,000** | **₹15,450** |

**Total potential additional saving: ₹45,900**

**Quick wins:**
1. 💊 **Parents' health insurance** — ₹50,000 deduction if parents are 60+ (saves ₹15,450)
2. 🏦 **NPS additional contribution** — ₹50,000 extra over 80C limit (saves ₹15,450)
3. 📈 **ELSS/PPF** — Top up ₹50,000 more in 80C bucket (saves ₹15,000)""",
    ),
    (
        ["gst", "itc", "gstr", "input.*tax", "2b", "3b", "notice.*gst"],
        """**GST ITC Risk Assessment** 🧾

For **Sunita Joshi** (BFXPJ5678S) — GSTIN 27BFXPJ5678S1Z5:

⚠️ **3 invoices flagged — ITC Risk Detected**

| Vendor | Invoice Date | ITC Amount | Status in 2B |
|---|---|---|---|
| Canva India Pvt Ltd | Sep 2024 | ₹5,400 | ❌ Not in 2B |
| Adobe Systems India | Aug 2024 | ₹3,600 | ❌ Not in 2B |
| Zoom Video India | Oct 2024 | ₹3,000 | ❌ Not in 2B |

**Total at-risk ITC: ₹12,000**

🚫 **Do NOT claim this ITC in GSTR-3B** until suppliers file their GSTR-1.

**Action required:**
1. Email/call each vendor to file their pending GSTR-1
2. Check GSTN portal → "ITC Comparison" section
3. Once supplier files, ITC will appear in next month's GSTR-2B
4. Risk of Section 16(2)(aa) disallowance if claimed without 2B matching""",
    ),
    (
        ["234e", "penalty", "late.*filing", "fine", "tds.*late"],
        """**Section 234E — Late Filing Fee Calculator** ⚠️

For **Sahyadri Software Solutions Pvt Ltd**:

| Quarter | Due Date | Filed On | Delay | TDS Amount | 234E Fee |
|---|---|---|---|---|---|
| Q2 FY 24-25 (26Q) | 31-Oct-2024 | 05-Nov-2024 | 5 days | ₹50,000 | **₹1,000** |

**Calculation:** ₹200/day × 5 days = ₹1,000
**Cap check:** Fee (₹1,000) < TDS amount (₹50,000) → ₹1,000 applies ✓

**How to pay:** ITNS 281 Challan → Minor Head 400 (TDS/TCS Regular Assessment)

> 💡 **Tip:** Set calendar reminders 5 days before due dates. Q4 (26Q) is due 31 May — this is most commonly missed.""",
    ),
    (
        ["advance tax", "installment", "quarterly", "advance.*payment"],
        """**Advance Tax Schedule — AY 2025-26** 📅

For **Rajesh Deshmukh** (Old Regime, Tax ₹90,168):

| Instalment | Due Date | Cumulative % | Amount to Pay |
|---|---|---|---|
| Q1 | **15 Jun 2024** | 15% | ₹13,525 |
| Q2 | **15 Sep 2024** | 45% | ₹40,575 (cumulative) |
| Q3 | **15 Dec 2024** | 75% | ₹67,626 (cumulative) |
| Q4 | **15 Mar 2025** | 100% | ₹90,168 (cumulative) |

> **Note:** If TDS fully covers your tax liability (as in Rajesh's case — ₹72,000 TDS vs ₹90,168 tax), you still need to pay the shortfall as advance tax.
>
> **Missing advance tax?** Interest u/s 234B (1%/month) and 234C (1%/month per quarter) will apply.""",
    ),
    (
        ["senior citizen", "pension", "80ttb", "pushpa kulkarni"],
        """**Senior Citizen Tax Planning** 👵

For **Pushpa Kulkarni** (DOB: 01-Sep-1953, age 71):

**Special benefits available:**

| Benefit | Section | Amount | Status |
|---|---|---|---|
| Higher basic exemption | Old Regime | ₹3,00,000 (vs ₹2,50,000) | ✅ Applied |
| FD/savings interest deduction | 80TTB | ₹50,000 | ✅ Claimed |
| Health insurance (self) | 80D | ₹50,000 | ✅ Claimed |
| Advance tax exemption | — | Nil advance tax needed | ✅ Applied |

**Result:** Net tax after rebate 87A = **₹0** ✅
**Refund expected:** ₹12,000 (TDS deducted by bank on FD)

> 💡 File ITR-1 early (July) to get refund processed quickly. Banks deduct TDS @ 10% on FD interest even when total income is below taxable limit.""",
    ),
    (
        ["plan", "subscription", "pricing", "cost", "upgrade", "professional", "starter"],
        """**TaxCompliance AI — Subscription Plans** 💳

| Plan | Price | Clients | AI Queries |
|---|---|---|---|
| **Free** | ₹0/month | 3 | 20/month |
| **Starter** | ₹999/month | 25 | 200/month |
| **Professional** | ₹2,499/month | 150 | 1,000/month |
| **Enterprise** | Custom | Unlimited | Unlimited |

> 🎭 **DEMO MODE:** Payments are simulated. No real charges in demo.
> In production, payments are processed via Razorpay. Annual plans save 25%.

For a CA firm with 50 clients: **Starter plan is ideal at ₹999/month.**
For 150+ clients: **Professional at ₹2,499/month (₹16/client/month).**""",
    ),
]

_DEFAULT_AI_RESPONSE = """**TaxCompliance AI — Demo Assistant** 🤖

I'm running in **demo mode** with pre-loaded sample data for 5 clients:

1. **Rajesh Deshmukh** — Salaried, ITR-1, Old regime saves ₹24,440
2. **Sunita Joshi** — Freelancer, ITR-4, GST registered, ITC mismatch found
3. **Sahyadri Software Solutions Pvt Ltd** — Company, TDS deductor, 234E penalty case
4. **Vikram Patil** — Business + Capital Gains, ITR-3
5. **Pushpa Kulkarni** — Senior Citizen, ITR-1, full refund of ₹12,000 due

Try asking me:
- "Which tax regime saves Rajesh more?"
- "What deductions is Rajesh missing?"
- "Explain the GST ITC mismatch for Sunita"
- "Calculate 234E penalty for Sahyadri Software"
- "What is the advance tax schedule?"
- "Explain 80TTB for senior citizens"

> In production mode, I analyse your actual client data — Form 26AS, GSTR-2B, challan statements — and give personalised, real-time answers."""


def get_mock_ai_response(message: str) -> str:
    """Return a canned AI response based on keyword matching."""
    msg_lower = message.lower()
    for keywords, response in _AI_RULES:
        for kw in keywords:
            if re.search(kw, msg_lower):
                return response
    return _DEFAULT_AI_RESPONSE
