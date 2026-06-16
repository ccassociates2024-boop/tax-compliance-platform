"""
AI Prompt Engineering for Tax Filing Assistant.
All prompts are structured for Claude (Anthropic) with Indian tax law context.
"""

SYSTEM_PROMPT_TAX_ASSISTANT = """
You are TaxAI, an expert Indian tax compliance assistant built into a professional CA software platform.

## Your Expertise
- Income Tax Act 1961 (all sections, deductions, exemptions) — full coverage of Chapters I-XXIII
- GST Act 2017 (CGST, SGST, IGST, Compensation Cess) and GST Rules
- TDS provisions (Chapter XVII-B & XVII-BB) — all sections (192-206)
- DTAA (Double Taxation Avoidance Agreements) — India's treaties with all countries
  (US, UK, UAE, Singapore, Mauritius, Germany, Netherlands, etc.), Article-wise relief
  (Article 4 residency tie-breaker, Article 7 business profits, Article 11/12 interest/royalty,
  Section 90/90A relief, Form 10F, Tax Residency Certificate requirements)
- TRACES portal, IT e-filing portal, GST portal workflows
- Assessment Year vs Financial Year distinctions
- Old vs New Tax Regime comparison (Section 115BAC)
- Capital gains (STCG/LTCG), indexation, grandfathering provisions
- Advance tax computation (Sections 207-211)
- Current Indian tax slabs, surcharge, cess rates
- International taxation: NRI taxation, Foreign Tax Credit (Rule 128), transfer pricing basics,
  POEM (Place of Effective Management), equalization levy

## Your Users
You assist Chartered Accountants, Company Secretaries, tax consultants, and their clients.
Answers must be precise, cite correct sections, and be practical for filing.

## Rules
1. Always specify which Financial Year / Assessment Year you're discussing
2. Cite the relevant section of Income Tax Act / GST Act / Rules
3. Flag any MISMATCHES you detect between data sources (AIS vs Form 16, GSTR-2B vs books)
4. Highlight DEADLINES and PENALTIES for non-compliance
5. If data is insufficient to give a definitive answer, list exactly what additional information is needed
6. Never fabricate tax figures — only compute from provided data
7. Recommend both Old and New regime when relevant, with computation comparison
8. Flag high audit-risk items clearly

## Response Format
- Use structured sections with headers
- Always show computations step-by-step
- Highlight amounts in Indian numbering (lakhs, crores)
- End with a summary of "Action Items" for the CA
"""

PROMPT_ITR_ANALYSIS = """
## Tax Data Analysis Request

**Client:** {client_name} | **PAN:** {pan} | **FY:** {financial_year} | **Client Type:** {client_type}

### Data Available:
**AIS Summary:**
{ais_data}

**Form 26AS:**
{form26as_data}

**Advance Tax Paid:**
{advance_tax_data}

**Documents provided:**
{documents_list}

---
Please:
1. Identify the correct ITR form (ITR-1/2/3/4/5/6) based on income sources
2. Compute income under each head with section references
3. Identify all applicable deductions (80C, 80D, 80CCD, 80G, 80TTA, HRA, LTA, etc.)
4. Compare Old Regime vs New Regime (show computation for both)
5. Compute final tax liability with surcharge and cess
6. Identify TDS credit available vs tax payable/refundable
7. Flag any MISMATCHES between AIS and 26AS data
8. List any missing information needed from client
9. Identify top 3 tax-saving opportunities for next year
10. Score audit risk (0-100) with reasons
"""

PROMPT_MISMATCH_DETECTION = """
## AIS vs 26AS Mismatch Analysis

**Client PAN:** {pan} | **FY:** {financial_year}

**AIS Data:**
{ais_data}

**Form 26AS Data:**
{form26as_data}

**Form 16 / TDS Certificates:**
{tds_data}

---
Analyze and report:
1. ALL mismatches between AIS and 26AS (amount differences, additional entries in AIS not in 26AS)
2. TDS shown in 26AS but missing in Form 16 (or vice versa)
3. Income shown in AIS but not declared in previous returns (if available)
4. High-value transactions in AIS that need explanation
5. SFT (Specified Financial Transactions) in AIS — explain impact
6. Recommended action for each mismatch:
   - Accept (if correct), Dispute (if incorrect), or Provide explanation
7. Risk level for each mismatch: LOW / MEDIUM / HIGH
"""

PROMPT_GST_WORKING = """
## GSTR-3B Working Preparation

**GSTIN:** {gstin} | **Period:** {period} | **Business:** {business_name}

### Sales Data (from GSTR-1 / Books):
{sales_data}

### Purchase Data (from GSTR-2B):
{gstr2b_data}

### Previous Month Cash/ITC Ledger Balance:
{ledger_balance}

---
Prepare complete GSTR-3B working:

**Table 3.1 — Outward Supplies:**
- 3.1(a) Taxable outward supplies: Compute IGST/CGST/SGST
- 3.1(b) Zero-rated supplies: Identify exports
- 3.1(c) Nil-rated and exempt
- 3.1(d) Inward supplies liable to reverse charge
- 3.1(e) Non-GST outward supplies

**Table 4 — ITC Available (from GSTR-2B):**
- 4(A) ITC as per GSTR-2B (IGST/CGST/SGST/Cess)
- 4(B) ITC reversal (Rule 42/43, non-business use)
- 4(D) Ineligible ITC (blocked credits u/s 17(5))
- Net ITC available

**Tax Payment Working:**
- Tax liability (Table 3.1)
- Less: ITC applied (IGST first, then CGST=SGST)
- Cash balance required
- Interest on delayed payment (if any)
- Late fee (if applicable)

**Final Summary:**
- Total tax payable via ITC: ___
- Total tax payable via cash: ___
- Challan amount needed: ___
"""

PROMPT_HSN_SUMMARY = """
## HSN/SAC Summary Generation for GSTR-1

**Business:** {business_name} | **Period:** {period}

**Invoice Data:**
{invoice_data}

---
Generate GSTR-1 HSN Summary table with:
1. Group all invoices by HSN/SAC code
2. For each HSN code provide:
   - HSN Code (4-digit or 6-digit as applicable based on turnover)
   - Description
   - UQC (Unit Quantity Code)
   - Total Quantity
   - Total Value
   - Taxable Value
   - IGST Amount
   - CGST Amount
   - SGST Amount
   - Cess Amount
3. Grand total row
4. Validate: Total taxable value should match GSTR-1 B2B + B2C + exports

Note: Businesses with turnover > 5 Cr must use 6-digit HSN; others can use 4-digit.
"""

PROMPT_TDS_COMPLIANCE = """
## TDS Compliance Check

**Deductor TAN:** {tan} | **FY:** {financial_year} | **Quarter:** {quarter}

### Deduction Details:
{deduction_data}

### Challans Deposited:
{challan_data}

### TRACES Defaults (if any):
{defaults_data}

---
Analyze TDS compliance and provide:

1. **Deduction Review:**
   - Verify correct rate applied for each deductee/payment type
   - Check threshold limits (Section-wise: 192, 193, 194, 194A, 194C, 194H, 194I, 194J, etc.)
   - Flag any Lower/NIL deduction certificates (Form 13/15G/15H) compliance

2. **Challan Matching:**
   - Total deducted vs total challan deposited
   - SHORT DEDUCTION (if any) with interest u/s 201(1A) computation
   - LATE DEPOSIT — identify and compute interest u/s 234E

3. **Filing Compliance:**
   - Due date for this quarter: {due_date}
   - Late filing fee u/s 234E: Rs. 200 per day (max = TDS amount)
   - Status: Filed / Not Filed / Correction required

4. **Action Items for CA:**
   - Immediate payments required
   - Correction statements needed
   - Estimated penalty exposure

5. **Year-end Summary:**
   - Total TDS deducted for FY
   - Form 16 / 16A generation status
"""

PROMPT_ADVANCE_TAX = """
## Advance Tax Computation

**Client:** {client_name} | **PAN:** {pan} | **FY:** {financial_year}

### Estimated Income for Year:
{estimated_income}

### Tax Paid So Far:
- Advance Tax Paid: {advance_tax_paid}
- TDS Expected: {expected_tds}

---
Compute advance tax installments:

**Under Old Regime / New Regime (whichever applicable):**

1. Estimated Total Income
2. Deductions (if Old Regime)
3. Net Taxable Income
4. Tax + Surcharge + Cess
5. Less: TDS (expected from employer/banks)
6. Net advance tax liability

**Installment Schedule (Section 211):**
| Installment | Due Date | Minimum % | Amount Due | Paid | Balance |
|---|---|---|---|---|---|
| 1st | 15-Jun-{year} | 15% | | | |
| 2nd | 15-Sep-{year} | 45% | | | |
| 3rd | 15-Dec-{year} | 75% | | | |
| 4th | 15-Mar-{year} | 100% | | | |

**Interest u/s 234B/234C if installments missed:**
{interest_computation}
"""

PROMPT_DEDUCTION_OPTIMIZER = """
## Tax Deduction Optimization

**Client:** {client_name} | **FY:** {financial_year} | **Regime:** Old Regime

### Current Investments/Expenses Declared:
{current_deductions}

### Income Level: {gross_income}

---
Identify ALL possible deductions the client can claim:

**Chapter VI-A Deductions:**
- 80C (Max 1.5L): LIC, PPF, ELSS, Home Loan Principal, Children Tuition, NSC, 5yr FD
  Currently used: {used_80c} | Balance available: {balance_80c}
- 80CCD(1B): NPS additional (Max 50,000)
- 80D: Mediclaim premium (self: 25K/50K, parents: 25K/50K senior)
- 80DD: Disabled dependent (75K or 1.25L)
- 80DDB: Medical treatment (40K or 1L for senior)
- 80E: Education loan interest (no limit, 8 years)
- 80EEA: Home loan interest (1.5L additional, affordable housing)
- 80G: Donations (50% or 100% as applicable)
- 80GGC: Political party donation (100%)
- 80TTA: Savings bank interest (max 10K)
- 80TTB: Senior citizen interest (max 50K)
- 80U: Disability (75K or 1.25L)

**Under Head Deductions:**
- Section 24(b): Home loan interest (max 2L for self-occupied)
- HRA exemption (House Rent Allowance) computation
- LTA exemption (2 times in 4-year block)
- Standard Deduction (50,000 for salaried)
- Professional tax (actual)

**Recommendations:**
List top 5 actionable deductions client should take before 31st March.
"""


def build_itr_prompt(client_data: dict, fetched_data: dict) -> str:
    """Build ITR analysis prompt from client and portal data."""
    return PROMPT_ITR_ANALYSIS.format(
        client_name=client_data.get("full_name", ""),
        pan=client_data.get("pan", ""),
        financial_year=fetched_data.get("financial_year", "2024-25"),
        client_type=client_data.get("client_type", "individual"),
        ais_data=_format_data(fetched_data.get("ais", {})),
        form26as_data=_format_data(fetched_data.get("form_26as", {})),
        advance_tax_data=_format_data(fetched_data.get("tax_payments", {})),
        documents_list=", ".join(fetched_data.get("documents", [])) or "None uploaded",
    )


def build_gst_prompt(client_data: dict, gst_data: dict) -> str:
    return PROMPT_GST_WORKING.format(
        gstin=client_data.get("gstin", ""),
        period=gst_data.get("period", ""),
        business_name=client_data.get("full_name", ""),
        sales_data=_format_data(gst_data.get("sales", {})),
        gstr2b_data=_format_data(gst_data.get("gstr2b", {})),
        ledger_balance=_format_data(gst_data.get("ledger", {})),
    )


def _format_data(data: dict) -> str:
    import json
    if not data:
        return "No data available"
    return json.dumps(data, indent=2, default=str)
