"""
GST API — GSTR-1, GSTR-3B, ITC reconciliation, HSN summary, notices.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import json, uuid

from database import get_db
from api.auth import get_current_user
from models import User, Client, GSTFiling, PortalFetchedData, PortalType
from services.credential_vault import CredentialVault
# NOTE: GSTPortalBot/LoginFailedException/CaptchaRequiredException are imported lazily
# inside the functions that use them — they depend on Playwright, which isn't needed
# (or installed) in demo mode.
from ai.tax_assistant import TaxAIAssistant

router = APIRouter()


class GSTCredentialRequest(BaseModel):
    client_id: str
    gstin: str
    username: str
    password: str


class FetchGSTDataRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"
    months: List[str]   # ["042024", "052024", ...]


class InvoiceUploadRequest(BaseModel):
    client_id: str
    period: str   # "042024"
    invoices: List[dict]


class GSTR3BWorkingRequest(BaseModel):
    client_id: str
    period: str
    sales_data: Optional[dict] = None


@router.post("/credentials")
async def store_gst_credentials(
    req: GSTCredentialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_client(req.client_id, current_user, db)
    vault = CredentialVault(db)
    await vault.store_credential(
        client_id=req.client_id,
        portal_type=PortalType.GST,
        username=req.username,
        password=req.password,
    )
    # Store GSTIN on client record
    result = await db.execute(select(Client).where(Client.id == req.client_id))
    client = result.scalar_one()
    client.gstin = req.gstin.upper()
    return {"message": "GST credentials stored securely"}


@router.post("/fetch")
async def fetch_gst_data(
    req: FetchGSTDataRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger background fetch of GSTR-2B, ledgers, notices from GST portal."""
    client = await _verify_client(req.client_id, current_user, db)
    vault = CredentialVault(db)
    creds = await vault.get_decrypted_password(req.client_id, PortalType.GST)
    if not creds:
        raise HTTPException(status_code=400, detail="No GST credentials stored")

    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        _run_gst_fetch,
        client_id=req.client_id,
        gstin=client.gstin,
        username=creds[0],
        password=creds[1],
        financial_year=req.financial_year,
        months=req.months,
        task_id=task_id,
    )
    return {"task_id": task_id, "message": "GST data fetch started"}


@router.post("/upload-invoices")
async def upload_invoices(
    req: InvoiceUploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload invoice list and auto-build GSTR-1 JSON."""
    from automation import GSTPortalBot

    client = await _verify_client(req.client_id, current_user, db)

    # Build GSTR-1 payload using AI + GST bot logic
    bot = GSTPortalBot()
    payload = bot._build_gstr1_payload(client.gstin, req.period, req.invoices)

    # Generate HSN summary via AI
    ai = TaxAIAssistant()
    hsn_summary = await ai.generate_hsn_summary(
        business_name=client.full_name,
        period=req.period,
        invoice_data=req.invoices,
    )

    # Save to filing record
    result = await db.execute(
        select(GSTFiling).where(
            GSTFiling.client_id == req.client_id,
            GSTFiling.tax_period == req.period,
            GSTFiling.return_type == "GSTR1",
        )
    )
    filing = result.scalar_one_or_none()

    if not filing:
        fy = _period_to_fy(req.period)
        filing = GSTFiling(
            client_id=req.client_id,
            financial_year=fy,
            tax_period=req.period,
            return_type="GSTR1",
        )
        db.add(filing)

    filing.gstr1_b2b = payload.get("b2b", [])
    filing.gstr1_b2c_small = payload.get("b2cs", [])
    filing.gstr1_hsn_summary = json.loads(hsn_summary) if hsn_summary.startswith("[") else {}
    filing.ai_notes = hsn_summary

    return {
        "period": req.period,
        "invoices_processed": len(req.invoices),
        "gstr1_payload": payload,
        "hsn_summary": hsn_summary,
    }


@router.post("/gstr3b-working")
async def get_gstr3b_working(
    req: GSTR3BWorkingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate complete GSTR-3B working using AI."""
    client = await _verify_client(req.client_id, current_user, db)

    # Fetch GSTR-2B data from DB
    result = await db.execute(
        select(PortalFetchedData).where(
            PortalFetchedData.client_id == req.client_id,
            PortalFetchedData.portal_type == PortalType.GST,
            PortalFetchedData.data_type == f"GSTR2B_{req.period}",
        )
    )
    gstr2b_record = result.scalar_one_or_none()
    gstr2b_data = json.loads(gstr2b_record.raw_data) if gstr2b_record else {}

    client_data = {
        "gstin": client.gstin,
        "full_name": client.full_name,
    }
    gst_data = {
        "period": req.period,
        "sales": req.sales_data or {},
        "gstr2b": gstr2b_data,
        "ledger": {},
    }

    async def stream_response():
        ai = TaxAIAssistant()
        async for chunk in ai.prepare_gst_working(client_data, gst_data):
            yield chunk

    return StreamingResponse(stream_response(), media_type="text/plain")


@router.get("/filings/{client_id}")
async def get_gst_filings(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_client(client_id, current_user, db)
    result = await db.execute(
        select(GSTFiling).where(GSTFiling.client_id == client_id)
                          .order_by(GSTFiling.tax_period.desc())
    )
    filings = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "period": f.tax_period,
            "return_type": f.return_type,
            "status": f.status.value,
            "arn": f.arn,
            "filed_at": f.filed_at,
            "tax_payable": f.gstr3b_tax_payable,
        }
        for f in filings
    ]


@router.post("/reconcile/{client_id}")
async def reconcile_itc(
    client_id: str,
    period: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reconcile GSTR-2B ITC with books of accounts."""
    client = await _verify_client(client_id, current_user, db)

    result = await db.execute(
        select(GSTFiling).where(
            GSTFiling.client_id == client_id,
            GSTFiling.tax_period == period,
        )
    )
    filing = result.scalar_one_or_none()
    if not filing:
        raise HTTPException(status_code=404, detail="GST filing not found for this period")

    gstr2b = filing.gstr2b_data or {}
    gstr1_b2b = filing.gstr1_b2b or []

    matched = []
    unmatched_in_2b = []
    unmatched_in_books = []

    gstr1_invoices = {inv.get("inum", ""): inv for b2b in gstr1_b2b for inv in b2b.get("inv", [])}
    for supplier in gstr2b.get("data", {}).get("b2b", []):
        for inv in supplier.get("inv", []):
            inv_no = inv.get("inum", "")
            if inv_no in gstr1_invoices:
                matched.append(inv_no)
            else:
                unmatched_in_2b.append(inv)

    reconciliation = {
        "period": period,
        "matched_count": len(matched),
        "unmatched_in_2b": len(unmatched_in_2b),
        "unmatched_in_books": len(unmatched_in_books),
        "details": {
            "unmatched_in_2b": unmatched_in_2b[:50],
        }
    }

    filing.reconciliation_result = reconciliation
    return reconciliation


async def _run_gst_fetch(client_id: str, gstin: str, username: str, password: str,
                          financial_year: str, months: list, task_id: str):
    from database import AsyncSessionLocal
    from automation import GSTPortalBot, LoginFailedException, CaptchaRequiredException
    from datetime import datetime

    async with AsyncSessionLocal() as db:
        try:
            async with GSTPortalBot(headless=True) as bot:
                # Note: GST portal login usually requires CAPTCHA handling
                # In production, integrate 2captcha or Anti-Captcha service
                data = await bot.fetch_all(gstin, username, password, financial_year, months)

            for key, content in data.items():
                record = PortalFetchedData(
                    client_id=client_id,
                    portal_type=PortalType.GST,
                    financial_year=financial_year,
                    data_type=key.upper(),
                    raw_data=json.dumps(content),
                    fetch_status="success",
                    fetched_at=datetime.utcnow(),
                )
                db.add(record)
            await db.commit()
        except Exception as e:
            record = PortalFetchedData(
                client_id=client_id,
                portal_type=PortalType.GST,
                financial_year=financial_year,
                data_type="FETCH_ERROR",
                fetch_status="failed",
                error_message=str(e),
            )
            db.add(record)
            await db.commit()


def _period_to_fy(period: str) -> str:
    """Convert "042024" -> "2024-25", "012025" -> "2024-25" """
    month = int(period[:2])
    year = int(period[2:])
    if month >= 4:
        return f"{year}-{str(year + 1)[-2:]}"
    else:
        return f"{year - 1}-{str(year)[-2:]}"


async def _verify_client(client_id: str, user: User, db: AsyncSession) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
