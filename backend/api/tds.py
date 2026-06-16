from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import json, uuid

from database import get_db
from api.auth import get_current_user
from models import User, Client, TDSFiling, PortalFetchedData, PortalType
from services.credential_vault import CredentialVault
# NOTE: TRACESBot/LoginFailedException/CaptchaRequiredException are imported lazily
# inside _run_traces_fetch() — they depend on Playwright, which isn't needed (or
# installed) in demo mode.
from ai.tax_assistant import TaxAIAssistant
from tds.tds_engine import (
    TDSEngine, TDSDeduction, TDSChallan, ReturnEntry26Q, TDS_SECTIONS, RETURN_DUE_DATES
)

router = APIRouter()


class TRACESCredentialRequest(BaseModel):
    client_id: str
    tan: str
    password: str
    login_type: str = "deductor"   # "deductor" or "taxpayer"
    dob: Optional[str] = None      # For taxpayer login: DD/MM/YYYY


class FetchTRACESRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"


class TDSComplianceRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"
    quarter: str = "Q1"


@router.post("/credentials")
async def store_traces_credentials(
    req: TRACESCredentialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_client(req.client_id, current_user, db)
    vault = CredentialVault(db)
    await vault.store_credential(
        client_id=req.client_id,
        portal_type=PortalType.TRACES,
        username=req.tan.upper(),
        password=req.password,
    )
    return {"message": "TRACES credentials stored"}


@router.post("/fetch")
async def fetch_traces_data(
    req: FetchTRACESRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = await _verify_client(req.client_id, current_user, db)
    vault = CredentialVault(db)
    creds = await vault.get_decrypted_password(req.client_id, PortalType.TRACES)
    if not creds:
        raise HTTPException(status_code=400, detail="No TRACES credentials stored")

    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        _run_traces_fetch,
        client_id=req.client_id,
        tan=creds[0],
        password=creds[1],
        financial_year=req.financial_year,
        is_deductor=client.is_tds_deductor,
        pan=client.pan,
        task_id=task_id,
    )
    return {"task_id": task_id, "message": "TRACES data fetch started"}


@router.post("/compliance-check")
async def tds_compliance_check(
    req: TDSComplianceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run AI-powered TDS compliance analysis for a quarter."""
    client = await _verify_client(req.client_id, current_user, db)

    result = await db.execute(
        select(PortalFetchedData).where(
            PortalFetchedData.client_id == req.client_id,
            PortalFetchedData.portal_type == PortalType.TRACES,
        )
    )
    records = result.scalars().all()
    fetched = {r.data_type: json.loads(r.raw_data) for r in records if r.raw_data}

    ai = TaxAIAssistant()
    analysis = await ai.check_tds_compliance(
        tan=client.tan or "N/A",
        financial_year=req.financial_year,
        quarter=req.quarter.replace("Q", ""),
        deduction_data=fetched.get(f"DEDUCTIONS_{req.quarter}", {}),
        challan_data=fetched.get(f"CHALLANS_{req.quarter}", {}),
        defaults_data=fetched.get("DEFAULTS", {}),
    )
    return {"compliance_analysis": analysis}


@router.get("/filings/{client_id}")
async def get_tds_filings(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_client(client_id, current_user, db)
    result = await db.execute(
        select(TDSFiling).where(TDSFiling.client_id == client_id)
                          .order_by(TDSFiling.financial_year.desc(), TDSFiling.quarter)
    )
    filings = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "financial_year": f.financial_year,
            "quarter": f.quarter,
            "form_type": f.form_type,
            "status": f.status.value,
            "total_tds": float(f.total_tds_amount or 0),
            "short_deduction": float(f.short_deduction or 0),
            "filed_at": f.filed_at,
        }
        for f in filings
    ]


class Compute234ERequest(BaseModel):
    quarter: str                   # Q1/Q2/Q3/Q4
    return_type: str = "26Q"       # 26Q / 24Q / 27Q
    actual_filing_date: Optional[str] = None   # ISO date or null
    total_tds_amount: float = 0


class ChallanMatchRequest(BaseModel):
    client_id: str
    quarter: str = "Q1"
    is_government_deductor: bool = False
    deductions: List[dict]
    challans: List[dict]


class TDSRateLookupRequest(BaseModel):
    section: str
    deductee_type: str = "resident"
    payment_amount: float = 0


class Validate26QRequest(BaseModel):
    tan: str
    deductor_name: str
    quarter: str
    financial_year: str = "2024-25"
    deductions: List[dict]
    challans: List[dict]


@router.post("/compute-234e")
async def compute_234e(
    req: Compute234ERequest,
    current_user: User = Depends(get_current_user),
):
    """Compute Section 234E late filing fee for a TDS return."""
    engine = TDSEngine()
    filing_date = date.fromisoformat(req.actual_filing_date) if req.actual_filing_date else None
    result = engine.compute_234e(req.quarter, req.return_type, filing_date, req.total_tds_amount)
    return {
        "quarter": result.quarter,
        "return_type": result.return_type,
        "due_date": str(result.due_date),
        "actual_filing_date": str(result.actual_filing_date),
        "delay_days": result.delay_days,
        "fee_per_day": result.fee_per_day,
        "total_fee_before_cap": round(result.total_fee, 2),
        "tds_amount_cap": round(result.max_fee_cap, 2),
        "applicable_fee": round(result.applicable_fee, 2),
        "waiver_possible": result.waiver_possible,
        "note": (
            "No 234E fee." if result.delay_days == 0
            else f"₹200/day × {result.delay_days} days = ₹{result.total_fee:,.2f}, "
                 f"capped at TDS amount ₹{result.max_fee_cap:,.2f}."
        ),
    }


@router.post("/match-challans")
async def match_challans(
    req: ChallanMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Match TDS deductions to challans; compute late deposit interest."""
    await _verify_client(req.client_id, current_user, db)
    engine = TDSEngine()

    deductions = [
        TDSDeduction(
            deductee_name=d.get("deductee_name", ""),
            deductee_pan=d.get("deductee_pan", ""),
            section=d.get("section", "194J"),
            payment_date=date.fromisoformat(d["payment_date"]),
            payment_amount=d.get("payment_amount", 0),
            tds_deducted=d.get("tds_deducted", 0),
            tds_deposited=d.get("tds_deposited", 0),
            challan_number=d.get("challan_number", ""),
            challan_date=date.fromisoformat(d["challan_date"]) if d.get("challan_date") else None,
            bsr_code=d.get("bsr_code", ""),
        )
        for d in req.deductions
    ]

    challans = [
        TDSChallan(
            challan_number=c.get("challan_number", ""),
            bsr_code=c.get("bsr_code", ""),
            deposit_date=date.fromisoformat(c["deposit_date"]),
            amount=c.get("amount", 0),
            section=c.get("section", ""),
            period_month=c.get("period_month", 1),
            period_year=c.get("period_year", 2025),
        )
        for c in req.challans
    ]

    matches = engine.match_challans(deductions, challans, req.is_government_deductor)

    return {
        "quarter": req.quarter,
        "total_deductions": len(deductions),
        "total_challans": len(challans),
        "matched": sum(1 for m in matches if m.status == "matched"),
        "unmatched": sum(1 for m in matches if m.status == "unmatched"),
        "short": sum(1 for m in matches if m.status == "short"),
        "total_interest_234c": round(sum(m.interest_234C for m in matches), 2),
        "results": [
            {
                "deductee_name": m.deduction.deductee_name,
                "deductee_pan": m.deduction.deductee_pan,
                "section": m.deduction.section,
                "payment_date": str(m.deduction.payment_date),
                "tds_deducted": m.deduction.tds_deducted,
                "tds_deposited": m.deduction.tds_deposited,
                "challan_number": m.matched_challan.challan_number if m.matched_challan else None,
                "status": m.status,
                "short_amount": m.short_amount,
                "delay_days": m.delay_days,
                "interest_234c": m.interest_234C,
                "remarks": m.remarks,
            }
            for m in matches
        ],
    }


@router.get("/rate-lookup")
async def tds_rate_lookup(
    section: str,
    deductee_type: str = "resident",
    payment_amount: float = 0,
    current_user: User = Depends(get_current_user),
):
    """Look up TDS rate and threshold for any section."""
    engine = TDSEngine()
    return engine.lookup_tds_rate(section, deductee_type, payment_amount)


@router.get("/sections")
async def list_tds_sections(current_user: User = Depends(get_current_user)):
    """Return full TDS section list with rates and thresholds."""
    return [
        {
            "section": sec,
            "description": info["description"],
            "rate_resident": info.get("rate_resident"),
            "threshold": info.get("threshold", 0),
        }
        for sec, info in TDS_SECTIONS.items()
    ]


@router.get("/return-due-dates")
async def return_due_dates(current_user: User = Depends(get_current_user)):
    """TDS return filing due dates — Q1 to Q4 FY 2024-25."""
    return [
        {
            "quarter": q,
            "period": info["period"],
            "due_date": str(info["due"]),
            "return_types": ["24Q", "26Q", "27Q", "27EQ"],
        }
        for q, info in RETURN_DUE_DATES.items()
    ]


@router.post("/validate-26q")
async def validate_26q(
    req: Validate26QRequest,
    current_user: User = Depends(get_current_user),
):
    """Validate 26Q data — PAN, sections, challan matching, totals."""
    engine = TDSEngine()

    entry = ReturnEntry26Q(
        tan=req.tan,
        deductor_name=req.deductor_name,
        quarter=req.quarter,
        financial_year=req.financial_year,
        deductions=[
            TDSDeduction(
                deductee_name=d.get("deductee_name", ""),
                deductee_pan=d.get("deductee_pan", ""),
                section=d.get("section", "194J"),
                payment_date=date.fromisoformat(d["payment_date"]),
                payment_amount=d.get("payment_amount", 0),
                tds_deducted=d.get("tds_deducted", 0),
                tds_deposited=d.get("tds_deposited", 0),
                challan_number=d.get("challan_number", ""),
            )
            for d in req.deductions
        ],
        challans=[
            TDSChallan(
                challan_number=c.get("challan_number", ""),
                bsr_code=c.get("bsr_code", ""),
                deposit_date=date.fromisoformat(c["deposit_date"]),
                amount=c.get("amount", 0),
                section=c.get("section", ""),
                period_month=c.get("period_month", 1),
                period_year=c.get("period_year", 2025),
            )
            for c in req.challans
        ],
    )

    return engine.validate_26q(entry)


@router.post("/validate-pan")
async def validate_pan(pan: str, current_user: User = Depends(get_current_user)):
    """Validate PAN format and return entity type."""
    return TDSEngine().validate_pan(pan)


async def _run_traces_fetch(client_id: str, tan: str, password: str,
                             financial_year: str, is_deductor: bool,
                             pan: str, task_id: str):
    from database import AsyncSessionLocal
    from automation import TRACESBot, LoginFailedException, CaptchaRequiredException
    from datetime import datetime

    async with AsyncSessionLocal() as db:
        try:
            async with TRACESBot(headless=True) as bot:
                if is_deductor:
                    data = await bot.fetch_all_deductor(tan, password, financial_year)
                else:
                    data = {}   # Taxpayer flow needs DOB — stored separately

            for key, content in data.items():
                if key in ("tan", "financial_year"):
                    continue
                record = PortalFetchedData(
                    client_id=client_id,
                    portal_type=PortalType.TRACES,
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
                portal_type=PortalType.TRACES,
                financial_year=financial_year,
                data_type="FETCH_ERROR",
                fetch_status="failed",
                error_message=str(e),
            )
            db.add(record)
            await db.commit()


async def _verify_client(client_id: str, user: User, db: AsyncSession) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
