"""
GST Data API — Excel upload, GSTR-1 builder, GSTR-3B engine, ITC reconciliation.
Extended GST endpoints beyond portal automation.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import json

from database import get_db
from api.auth import get_current_user
from models import User, Client, GSTFiling
from gst import (
    ExcelParser, InvoiceOCRParser, generate_excel_template,
    GSTR1Builder, GSTR3BComputer, OutwardSupplySummary, ITCData, LedgerBalance,
    ITCReconciliationEngine, PurchaseInvoice, GSTR2BInvoice,
    lookup_hsn, suggest_hsn, get_gst_rate,
)
from ai.tax_assistant import TaxAIAssistant

router = APIRouter()


# ─── TEMPLATE DOWNLOAD ───────────────────────────────────────────────────────

@router.get("/template/download")
async def download_invoice_template(
    gstin: str = Query(..., description="Supplier GSTIN"),
    current_user: User = Depends(get_current_user),
):
    """Download the standard Excel invoice upload template."""
    template_bytes = generate_excel_template(gstin)
    return Response(
        content=template_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=gst_invoice_template_{gstin}.xlsx"
        },
    )


# ─── EXCEL / CSV UPLOAD ───────────────────────────────────────────────────────

@router.post("/upload/excel/{client_id}")
async def upload_invoice_excel(
    client_id: str,
    period: str = Query(..., description="Tax period e.g. 042024"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload Excel/CSV invoice file.
    Auto-parses, validates, builds GSTR-1 JSON, generates HSN summary.
    """
    client = await _get_client(client_id, current_user, db)
    if not client.gstin:
        raise HTTPException(status_code=400, detail="Client has no GSTIN registered")

    file_bytes = await file.read()
    state_code = client.gstin[:2]

    parser = ExcelParser(
        supplier_gstin=client.gstin,
        supplier_state=state_code,
    )
    parse_result = parser.parse_file(file_bytes, file.filename)

    if "error" in parse_result:
        raise HTTPException(status_code=400, detail=parse_result["error"])

    invoices = parse_result["invoices"]
    if not invoices:
        return {
            "message": "No invoices found in file",
            "parse_errors": parse_result.get("parse_errors", []),
        }

    # Build GSTR-1 JSON
    builder = GSTR1Builder(client.gstin, period, state_code)
    gstr1_result = builder.build(invoices)

    # Save to DB
    await _save_gstr1(client_id, period, gstr1_result, db)

    # AI-generated HSN summary analysis
    ai = TaxAIAssistant()
    hsn_notes = await ai.generate_hsn_summary(
        business_name=client.full_name,
        period=period,
        invoice_data=[
            {
                "invoice_number": inv.invoice_number,
                "hsn_sac": inv.items[0].hsn_sac if inv.items else "",
                "description": inv.items[0].description if inv.items else "",
                "taxable_value": inv.taxable_value,
                "gst_rate": inv.items[0].gst_rate if inv.items else 18,
                "igst": inv.igst_amount,
                "cgst": inv.cgst_amount,
                "sgst": inv.sgst_amount,
            }
            for inv in invoices
        ],
    )

    return {
        "message": "File processed successfully",
        "parse_summary": {
            "total_rows": parse_result["total_rows"],
            "parsed_invoices": parse_result["parsed_invoices"],
            "error_rows": parse_result["error_rows"],
        },
        "gstr1_summary": gstr1_result["summary"],
        "validation_errors": gstr1_result["validation_errors"],
        "hsn_summary": gstr1_result["payload"]["hsn"]["data"],
        "hsn_analysis": hsn_notes,
        "gstr1_payload": gstr1_result["payload"],
    }


@router.post("/upload/pdf/{client_id}")
async def upload_invoice_pdf(
    client_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF invoice and extract data via OCR."""
    await _get_client(client_id, current_user, db)

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    pdf_bytes = await file.read()
    ocr = InvoiceOCRParser()
    extracted = ocr.parse_pdf(pdf_bytes)

    return {
        "extracted_data": extracted,
        "message": "Review and confirm the extracted data",
    }


# ─── HSN LOOKUP ───────────────────────────────────────────────────────────────

@router.get("/hsn/lookup")
async def hsn_lookup(
    code: Optional[str] = Query(None, description="HSN/SAC code"),
    keyword: Optional[str] = Query(None, description="Search by description"),
    current_user: User = Depends(get_current_user),
):
    """Look up HSN/SAC code with GST rates, or search by keyword."""
    if code:
        result = lookup_hsn(code)
        if result:
            return result
        raise HTTPException(status_code=404, detail=f"HSN code {code} not found")

    if keyword:
        results = suggest_hsn(keyword)
        return {"results": results, "count": len(results)}

    raise HTTPException(status_code=400, detail="Provide either 'code' or 'keyword'")


@router.get("/hsn/rate")
async def hsn_rate(
    code: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Get GST rate for an HSN/SAC code."""
    return get_gst_rate(code)


# ─── GSTR-3B COMPUTATION ─────────────────────────────────────────────────────

class GSTR3BRequest(BaseModel):
    client_id: str
    period: str

    # Outward supplies
    taxable_igst: float = 0
    taxable_cgst: float = 0
    taxable_sgst: float = 0
    taxable_cess: float = 0
    taxable_value: float = 0
    zero_rated_value: float = 0
    zero_rated_igst: float = 0
    nil_exempt_value: float = 0
    non_gst_value: float = 0
    rcm_taxable_value: float = 0
    rcm_igst: float = 0
    rcm_cgst: float = 0
    rcm_sgst: float = 0

    # ITC (from GSTR-2B)
    b2b_igst: float = 0
    b2b_cgst: float = 0
    b2b_sgst: float = 0
    b2b_cess: float = 0
    import_goods_igst: float = 0
    import_services_igst: float = 0
    rcm_itc_igst: float = 0
    rcm_itc_cgst: float = 0
    rcm_itc_sgst: float = 0
    rule_42_43_igst: float = 0
    rule_42_43_cgst: float = 0
    rule_42_43_sgst: float = 0

    # Opening ledger
    opening_igst: float = 0
    opening_cgst: float = 0
    opening_sgst: float = 0
    opening_cess: float = 0

    # Filing date (for interest/late fee computation)
    filing_date: Optional[str] = None   # DD/MM/YYYY


@router.post("/gstr3b/compute")
async def compute_gstr3b(
    req: GSTR3BRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute full GSTR-3B: ITC utilization, tax payable, interest, late fee, challan amount.
    """
    client = await _get_client(req.client_id, current_user, db)

    from datetime import date, datetime
    filing_date = date.today()
    if req.filing_date:
        try:
            filing_date = datetime.strptime(req.filing_date, "%d/%m/%Y").date()
        except ValueError:
            pass

    outward = OutwardSupplySummary(
        taxable_igst=req.taxable_igst,
        taxable_cgst=req.taxable_cgst,
        taxable_sgst=req.taxable_sgst,
        taxable_cess=req.taxable_cess,
        taxable_value=req.taxable_value,
        zero_rated_value=req.zero_rated_value,
        zero_rated_igst=req.zero_rated_igst,
        nil_exempt_value=req.nil_exempt_value,
        non_gst_value=req.non_gst_value,
        rcm_taxable_value=req.rcm_taxable_value,
        rcm_igst=req.rcm_igst,
        rcm_cgst=req.rcm_cgst,
        rcm_sgst=req.rcm_sgst,
    )

    itc = ITCData(
        b2b_igst=req.b2b_igst,
        b2b_cgst=req.b2b_cgst,
        b2b_sgst=req.b2b_sgst,
        b2b_cess=req.b2b_cess,
        import_goods_igst=req.import_goods_igst,
        import_services_igst=req.import_services_igst,
        rcm_igst=req.rcm_itc_igst,
        rcm_cgst=req.rcm_itc_cgst,
        rcm_sgst=req.rcm_itc_sgst,
        rule_42_43_igst=req.rule_42_43_igst,
        rule_42_43_cgst=req.rule_42_43_cgst,
        rule_42_43_sgst=req.rule_42_43_sgst,
    )

    opening = LedgerBalance(
        igst=req.opening_igst,
        cgst=req.opening_cgst,
        sgst=req.opening_sgst,
        cess=req.opening_cess,
    )

    computer = GSTR3BComputer(
        gstin=client.gstin,
        period=req.period,
        filing_date=filing_date,
    )
    result = computer.compute(outward, itc, opening, LedgerBalance())

    # Save to filing record
    filing_result = await db.execute(
        select(GSTFiling).where(
            GSTFiling.client_id == req.client_id,
            GSTFiling.tax_period == req.period,
            GSTFiling.return_type == "GSTR3B",
        )
    )
    filing = filing_result.scalar_one_or_none()
    if not filing:
        from models.tax_filing import FilingStatus
        filing = GSTFiling(
            client_id=req.client_id,
            financial_year=_period_to_fy(req.period),
            tax_period=req.period,
            return_type="GSTR3B",
        )
        db.add(filing)

    filing.gstr3b_outward_taxable = req.taxable_value
    filing.gstr3b_tax_payable = result["challan_summary"]
    filing.gstr3b_itc_available = result["net_itc_available"]
    filing.gstr3b_interest = result["interest"].get("igst", 0) + result["interest"].get("cgst", 0) + result["interest"].get("sgst", 0)
    filing.gstr3b_late_fee = result["late_fee"]

    return result


# ─── ITC RECONCILIATION ───────────────────────────────────────────────────────

class ReconcileRequest(BaseModel):
    client_id: str
    period: str
    purchase_invoices: List[dict]    # Books data
    gstr2b_invoices: List[dict]      # GSTR-2B data


@router.post("/reconcile/itc")
async def reconcile_itc(
    req: ReconcileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full ITC reconciliation: GSTR-2B vs purchase books.
    Returns matched, mismatched, only-in-2B, only-in-books, blocked credits.
    """
    await _get_client(req.client_id, current_user, db)

    books = [
        PurchaseInvoice(
            supplier_gstin=inv.get("supplier_gstin", ""),
            supplier_name=inv.get("supplier_name", ""),
            invoice_number=inv.get("invoice_number", ""),
            invoice_date=inv.get("invoice_date", ""),
            invoice_value=float(inv.get("invoice_value", 0)),
            taxable_value=float(inv.get("taxable_value", 0)),
            igst=float(inv.get("igst", 0)),
            cgst=float(inv.get("cgst", 0)),
            sgst=float(inv.get("sgst", 0)),
            cess=float(inv.get("cess", 0)),
            hsn_sac=inv.get("hsn_sac", ""),
            is_rcm=inv.get("is_rcm", False),
        )
        for inv in req.purchase_invoices
    ]

    gstr2b = [
        GSTR2BInvoice(
            supplier_gstin=inv.get("ctin", ""),
            supplier_name=inv.get("trdnm", ""),
            supplier_trade_name=inv.get("trdnm", ""),
            invoice_number=inv.get("inum", ""),
            invoice_date=inv.get("idt", ""),
            invoice_type=inv.get("inv_typ", "B2B"),
            invoice_value=float(inv.get("val", 0)),
            taxable_value=float(inv.get("txval", 0)),
            igst=float(inv.get("iamt", 0)),
            cgst=float(inv.get("camt", 0)),
            sgst=float(inv.get("samt", 0)),
            cess=float(inv.get("csamt", 0)),
            itc_availability=inv.get("itcavl", "Yes"),
        )
        for inv in req.gstr2b_invoices
    ]

    engine = ITCReconciliationEngine()
    result = engine.reconcile(books, gstr2b)

    return {
        "summary": result.summary,
        "matched": result.matched[:100],
        "mismatched": result.mismatched[:100],
        "only_in_2b": result.only_in_2b[:50],
        "only_in_books": result.only_in_books[:50],
        "blocked_credits": result.blocked_credits[:50],
        "total_matched": len(result.matched),
        "total_mismatched": len(result.mismatched),
        "total_only_in_2b": len(result.only_in_2b),
        "total_only_in_books": len(result.only_in_books),
        "total_blocked": len(result.blocked_credits),
    }


def _period_to_fy(period: str) -> str:
    month = int(period[:2])
    year = int(period[2:])
    return f"{year}-{str(year + 1)[-2:]}" if month >= 4 else f"{year - 1}-{str(year)[-2:]}"


async def _get_client(client_id: str, user: User, db: AsyncSession) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def _save_gstr1(client_id: str, period: str, gstr1_result: dict, db: AsyncSession):
    from models.tax_filing import FilingStatus
    result = await db.execute(
        select(GSTFiling).where(
            GSTFiling.client_id == client_id,
            GSTFiling.tax_period == period,
            GSTFiling.return_type == "GSTR1",
        )
    )
    filing = result.scalar_one_or_none()
    if not filing:
        filing = GSTFiling(
            client_id=client_id,
            financial_year=_period_to_fy(period),
            tax_period=period,
            return_type="GSTR1",
        )
        db.add(filing)

    payload = gstr1_result.get("payload", {})
    filing.gstr1_b2b = payload.get("b2b", [])
    filing.gstr1_b2c_small = payload.get("b2cs", [])
    filing.gstr1_b2c_large = payload.get("b2cl", [])
    filing.gstr1_exp = payload.get("exp", [])
    filing.gstr1_cdnr = payload.get("cdnr", [])
    filing.gstr1_hsn_summary = payload.get("hsn", {}).get("data", [])
    filing.gstr1_doc_summary = payload.get("doc_issue", {}).get("doc_det", [])
