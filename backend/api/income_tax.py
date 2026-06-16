"""
Income Tax API — fetch from IT Portal, compute ITR, store results.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from database import get_db
from api.auth import get_current_user
from models import User, Client, ITRFiling, PortalFetchedData, PortalType
from services.credential_vault import CredentialVault
# NOTE: ITPortalBot/LoginFailedException/CaptchaRequiredException are imported lazily
# inside _run_it_fetch() — they depend on Playwright, which isn't needed (or installed)
# in demo mode. Keeping this import at module scope would crash the whole app on boot
# if Playwright browsers aren't present.
from income_tax.itr_engine import (
    ITREngine, ITRInput, SalaryIncome, HousePropertyIncome, CapitalGainsIncome,
    BusinessIncome, OtherSourcesIncome, AdvanceTaxPaid, TDSCredit,
)
from income_tax.deductions import DeductionInput

router = APIRouter()


class FetchITDataRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"


class StoreCredentialRequest(BaseModel):
    client_id: str
    pan: str
    password: str


@router.post("/credentials")
async def store_it_credentials(
    req: StoreCredentialRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store encrypted IT portal credentials for a client."""
    await _verify_client_ownership(req.client_id, current_user, db)

    vault = CredentialVault(db)
    await vault.store_credential(
        client_id=req.client_id,
        portal_type=PortalType.INCOME_TAX,
        username=req.pan.upper(),
        password=req.password,
    )
    return {"message": "Credentials stored securely"}


@router.post("/fetch")
async def fetch_it_data(
    req: FetchITDataRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger IT portal data fetch (runs in background).
    Returns immediately with a task_id to poll for status.
    """
    await _verify_client_ownership(req.client_id, current_user, db)

    vault = CredentialVault(db)
    creds = await vault.get_decrypted_password(req.client_id, PortalType.INCOME_TAX)
    if not creds:
        raise HTTPException(status_code=400, detail="No IT portal credentials found for this client")

    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        _run_it_fetch,
        client_id=req.client_id,
        pan=creds[0],
        password=creds[1],
        financial_year=req.financial_year,
        task_id=task_id,
    )
    return {"task_id": task_id, "message": "Data fetch started"}


@router.get("/data/{client_id}")
async def get_fetched_data(
    client_id: str,
    financial_year: str = "2024-25",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all fetched IT portal data for a client."""
    await _verify_client_ownership(client_id, current_user, db)

    result = await db.execute(
        select(PortalFetchedData).where(
            PortalFetchedData.client_id == client_id,
            PortalFetchedData.portal_type == PortalType.INCOME_TAX,
            PortalFetchedData.financial_year == financial_year,
        )
    )
    records = result.scalars().all()

    return {
        "client_id": client_id,
        "financial_year": financial_year,
        "data": [
            {
                "data_type": r.data_type,
                "fetch_status": r.fetch_status,
                "fetched_at": r.fetched_at,
                "has_data": bool(r.raw_data),
            }
            for r in records
        ]
    }


@router.get("/itr/{client_id}")
async def get_itr_filings(
    client_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all ITR filings for a client."""
    await _verify_client_ownership(client_id, current_user, db)

    result = await db.execute(
        select(ITRFiling).where(ITRFiling.client_id == client_id)
                         .order_by(ITRFiling.created_at.desc())
    )
    filings = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "financial_year": f.financial_year,
            "assessment_year": f.assessment_year,
            "itr_form": f.itr_form,
            "status": f.status.value,
            "total_taxable_income": float(f.total_taxable_income or 0),
            "tax_payable_refundable": float(f.tax_payable_refundable or 0),
            "ai_risk_score": f.ai_risk_score,
            "tax_regime": f.tax_regime,
            "filed_at": f.filed_at,
            "acknowledgement_number": f.acknowledgement_number,
        }
        for f in filings
    ]


async def _run_it_fetch(client_id: str, pan: str, password: str,
                         financial_year: str, task_id: str):
    """Background task: run IT portal bot and store results."""
    from database import AsyncSessionLocal
    from automation import ITPortalBot, LoginFailedException, CaptchaRequiredException
    import json

    async with AsyncSessionLocal() as db:
        try:
            async with ITPortalBot(headless=True) as bot:
                data = await bot.fetch_all(pan, password, financial_year)

            # Store each data type
            for data_type, content in data.items():
                record = PortalFetchedData(
                    client_id=client_id,
                    portal_type=PortalType.INCOME_TAX,
                    financial_year=financial_year,
                    data_type=data_type.upper(),
                    raw_data=json.dumps(content),
                    fetch_status="success" if "error" not in content else "failed",
                    error_message=content.get("error") if "error" in content else None,
                )
                from datetime import datetime
                record.fetched_at = datetime.utcnow()
                db.add(record)

            await db.commit()

        except (LoginFailedException, CaptchaRequiredException) as e:
            record = PortalFetchedData(
                client_id=client_id,
                portal_type=PortalType.INCOME_TAX,
                financial_year=financial_year,
                data_type="LOGIN_ERROR",
                fetch_status="failed",
                error_message=str(e),
            )
            db.add(record)
            await db.commit()


class ComputeITRRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"
    age: int = 30
    entity_type: str = "individual"
    preferred_regime: str = "auto"

    # Salary
    gross_salary: float = 0
    basic_salary: float = 0
    hra_component: float = 0
    hra_exempt: float = 0
    lta_exempt: float = 0
    other_exempt_allowances: float = 0
    perquisites: float = 0
    tds_by_employer: float = 0

    # House property
    annual_letable_value: float = 0
    municipal_tax_paid: float = 0
    home_loan_interest_24b: float = 0
    is_self_occupied: bool = True

    # Capital gains
    stcg_111a: float = 0
    stcg_other: float = 0
    ltcg_112a: float = 0
    ltcg_other: float = 0

    # Business
    business_net_profit: float = 0
    is_presumptive: bool = False
    presumptive_section: str = ""
    turnover: float = 0
    presumptive_rate: float = 8.0

    # Other sources
    interest_savings: float = 0
    interest_fd: float = 0
    dividend: float = 0
    family_pension: float = 0
    other_income: float = 0

    # Deductions
    lic_premium: float = 0
    ppf: float = 0
    epf: float = 0
    elss: float = 0
    home_loan_principal: float = 0
    nsc: float = 0
    tuition_fees: float = 0
    five_yr_fd: float = 0
    sukanya_samriddhi: float = 0
    other_80c: float = 0
    nps_employee_80ccd1: float = 0
    nps_additional_80ccd1b: float = 0
    nps_employer_80ccd2: float = 0
    mediclaim_self_family: float = 0
    mediclaim_self_senior: bool = False
    mediclaim_parents: float = 0
    mediclaim_parents_senior: bool = False
    preventive_health_checkup: float = 0
    education_loan_interest: float = 0
    donation_100_percent: float = 0
    donation_50_percent: float = 0
    rent_paid_80gg: float = 0
    savings_interest_80tta: float = 0
    senior_interest_80ttb: float = 0
    hra_received: float = 0
    basic_da_for_hra: float = 0
    rent_paid_actual: float = 0
    is_metro: bool = False
    professional_tax: float = 0
    lta_exemption: float = 0
    is_salaried: bool = True

    # Advance tax paid
    advance_tax_q1: float = 0
    advance_tax_q2: float = 0
    advance_tax_q3: float = 0
    advance_tax_q4: float = 0

    # TDS / TCS
    tds_26as_other: float = 0
    tcs_collected: float = 0
    self_assessment_tax: float = 0


def _build_itr_input(req: ComputeITRRequest) -> ITRInput:
    sal = SalaryIncome(
        gross_salary=req.gross_salary,
        basic_salary=req.basic_salary,
        hra_component=req.hra_component,
        hra_exempt=req.hra_exempt,
        lta_exempt=req.lta_exempt,
        other_exempt_allowances=req.other_exempt_allowances,
        perquisites=req.perquisites,
        tds_by_employer=req.tds_by_employer,
    )

    hp = HousePropertyIncome(
        annual_letable_value=req.annual_letable_value,
        municipal_tax_paid=req.municipal_tax_paid,
        home_loan_interest=req.home_loan_interest_24b,
        is_self_occupied=req.is_self_occupied,
    )

    cg = CapitalGainsIncome(
        stcg_111a=req.stcg_111a,
        stcg_other=req.stcg_other,
        ltcg_112a=req.ltcg_112a,
        ltcg_other=req.ltcg_other,
    )

    biz = BusinessIncome(
        net_profit=req.business_net_profit,
        is_presumptive=req.is_presumptive,
        presumptive_section=req.presumptive_section,
        turnover=req.turnover,
        presumptive_rate=req.presumptive_rate,
    )

    os = OtherSourcesIncome(
        interest_savings=req.interest_savings,
        interest_fd=req.interest_fd,
        dividend=req.dividend,
        family_pension=req.family_pension,
        other=req.other_income,
    )

    ded = DeductionInput(
        lic_premium=req.lic_premium, ppf=req.ppf, epf=req.epf, elss=req.elss,
        home_loan_principal=req.home_loan_principal, nsc=req.nsc,
        tuition_fees=req.tuition_fees, five_yr_fd=req.five_yr_fd,
        sukanya_samriddhi=req.sukanya_samriddhi, other_80c=req.other_80c,
        nps_employee_80ccd1=req.nps_employee_80ccd1,
        nps_additional_80ccd1b=req.nps_additional_80ccd1b,
        nps_employer_80ccd2=req.nps_employer_80ccd2,
        mediclaim_self_family=req.mediclaim_self_family,
        mediclaim_self_senior=req.mediclaim_self_senior,
        mediclaim_parents=req.mediclaim_parents,
        mediclaim_parents_senior=req.mediclaim_parents_senior,
        preventive_health_checkup=req.preventive_health_checkup,
        education_loan_interest=req.education_loan_interest,
        donation_100_percent=req.donation_100_percent,
        donation_50_percent=req.donation_50_percent,
        rent_paid_80gg=req.rent_paid_80gg,
        savings_interest_80tta=req.savings_interest_80tta,
        senior_interest_80ttb=req.senior_interest_80ttb,
        home_loan_interest_24b=req.home_loan_interest_24b,
        hra_received=req.hra_received,
        basic_da_for_hra=req.basic_da_for_hra,
        rent_paid_actual=req.rent_paid_actual,
        is_metro=req.is_metro,
        professional_tax=req.professional_tax,
        lta_exemption=req.lta_exemption,
        is_salaried=req.is_salaried,
    )

    at = AdvanceTaxPaid(
        q1_june=req.advance_tax_q1,
        q2_sep=req.advance_tax_q2,
        q3_dec=req.advance_tax_q3,
        q4_march=req.advance_tax_q4,
    )

    tds = TDSCredit(
        tds_salary=req.tds_by_employer,
        tds_26as_other=req.tds_26as_other,
        tcs_collected=req.tcs_collected,
    )

    return ITRInput(
        age=req.age,
        entity_type=req.entity_type,
        preferred_regime=req.preferred_regime,
        salary=sal,
        house_properties=[hp] if any([
            req.annual_letable_value, req.home_loan_interest_24b,
            not req.is_self_occupied
        ]) else [],
        capital_gains=cg,
        business=biz,
        other_sources=os,
        deductions=ded,
        advance_tax=at,
        tds=tds,
        self_assessment_tax=req.self_assessment_tax,
    )


@router.post("/compute")
async def compute_itr(
    req: ComputeITRRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compute full ITR — Old vs New regime comparison, ITR form selector,
    deduction optimizer, advance tax schedule.
    """
    await _verify_client_ownership(req.client_id, current_user, db)

    itr_input = _build_itr_input(req)
    result = ITREngine().compute(itr_input)

    def _tc_dict(tc):
        return {
            "regime": tc.regime,
            "gross_total_income": round(tc.gross_total_income, 2),
            "total_deductions": round(tc.total_deductions, 2),
            "taxable_income": round(tc.taxable_income, 2),
            "basic_tax": round(tc.basic_tax, 2),
            "tax_on_stcg_111a": round(tc.tax_on_stcg_111a, 2),
            "tax_on_ltcg_112a": round(tc.tax_on_ltcg_112a, 2),
            "tax_on_ltcg_other": round(tc.tax_on_ltcg_other, 2),
            "total_tax_before_surcharge": round(tc.total_tax_before_surcharge, 2),
            "surcharge": round(tc.surcharge, 2),
            "health_edu_cess": round(tc.health_edu_cess, 2),
            "total_tax_liability": round(tc.total_tax_liability, 2),
            "rebate_87a": round(tc.rebate_87a, 2),
            "net_tax_payable": round(tc.net_tax_payable, 2),
            "advance_tax_paid": round(tc.advance_tax_paid, 2),
            "tds_credit": round(tc.tds_credit, 2),
            "self_assessment_tax": round(tc.self_assessment_tax, 2),
            "total_tax_paid": round(tc.total_tax_paid, 2),
            "tax_payable_refundable": round(tc.tax_payable_refundable, 2),
            "deductions_breakdown": tc.deduction_result.breakdown,
        }

    return {
        "itr_form": result.itr_form.value,
        "itr_form_reason": result.itr_form_reason,
        "income_summary": {
            "salary_taxable": round(result.income_summary.salary_taxable, 2),
            "house_property": round(result.income_summary.house_property, 2),
            "business_income": round(result.income_summary.business_income, 2),
            "stcg_111a": round(result.income_summary.stcg_111a, 2),
            "stcg_other": round(result.income_summary.stcg_other, 2),
            "ltcg_112a_taxable": round(result.income_summary.ltcg_112a_taxable, 2),
            "ltcg_other": round(result.income_summary.ltcg_other, 2),
            "other_sources": round(result.income_summary.other_sources, 2),
            "gross_total_income": round(result.income_summary.gross_total_income, 2),
        },
        "old_regime": _tc_dict(result.old_regime),
        "new_regime": _tc_dict(result.new_regime),
        "comparison": {
            "recommended_regime": result.comparison.recommended_regime,
            "savings": round(result.comparison.savings, 2),
            "recommendation_reason": result.comparison.recommendation_reason,
        },
        "advance_tax_schedule": result.advance_tax_schedule,
        "deduction_optimizer_tips": result.deduction_optimizer_tips,
    }


async def _verify_client_ownership(client_id: str, user: User, db: AsyncSession):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.owner_id == user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
