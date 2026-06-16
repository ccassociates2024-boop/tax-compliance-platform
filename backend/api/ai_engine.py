"""
AI Engine API — streaming AI analysis, chat, risk scoring, deduction optimizer.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import json

from config import get_settings
from database import get_db
from api.auth import get_current_user
from models import User, Client, PortalFetchedData, PortalType
from ai.tax_assistant import TaxAIAssistant

router = APIRouter()
settings = get_settings()


class ChatMessage(BaseModel):
    role: str   # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    client_id: Optional[str] = None
    messages: List[ChatMessage]


class ITRAnalysisRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"


class DeductionOptimizerRequest(BaseModel):
    client_id: str
    financial_year: str = "2024-25"
    gross_income: float
    current_deductions: dict = {}


@router.post("/chat")
async def ai_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streaming AI chat with tax assistant. Supports full conversation history."""
    client_context = None
    if req.client_id:
        result = await db.execute(
            select(Client).where(
                Client.id == req.client_id,
                Client.owner_id == current_user.id,
            )
        )
        client = result.scalar_one_or_none()
        if client:
            client_context = {
                "client_name": client.full_name,
                "pan": client.pan,
                "gstin": client.gstin,
                "client_type": client.client_type.value,
                "current_fy": client.current_fy,
                "is_tds_deductor": client.is_tds_deductor,
            }

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if settings.DEMO_MODE:
        from demo.mock_data import get_mock_ai_response
        last_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        response_text = get_mock_ai_response(last_user_message)

        async def demo_stream():
            chunk_size = 12
            for i in range(0, len(response_text), chunk_size):
                yield response_text[i : i + chunk_size]

        return StreamingResponse(demo_stream(), media_type="text/plain")

    async def stream():
        ai = TaxAIAssistant()
        async for chunk in ai.chat(messages, client_context):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")


@router.post("/analyze-itr")
async def analyze_itr(
    req: ITRAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full AI-powered ITR analysis: streams regime comparison, deductions,
    tax computation, mismatch flags, and risk score.
    """
    result = await db.execute(
        select(Client).where(
            Client.id == req.client_id,
            Client.owner_id == current_user.id,
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Fetch all IT portal data for this FY
    data_result = await db.execute(
        select(PortalFetchedData).where(
            PortalFetchedData.client_id == req.client_id,
            PortalFetchedData.portal_type == PortalType.INCOME_TAX,
            PortalFetchedData.financial_year == req.financial_year,
            PortalFetchedData.fetch_status == "success",
        )
    )
    fetched_records = data_result.scalars().all()

    fetched_data = {"financial_year": req.financial_year}
    for record in fetched_records:
        if record.raw_data:
            fetched_data[record.data_type.lower()] = json.loads(record.raw_data)

    client_data = {
        "full_name": client.full_name,
        "pan": client.pan,
        "client_type": client.client_type.value,
    }

    async def stream():
        ai = TaxAIAssistant()
        async for chunk in ai.analyze_itr(client_data, fetched_data):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")


@router.post("/risk-score/{client_id}")
async def get_risk_score(
    client_id: str,
    financial_year: str = "2024-25",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compute AI audit risk score (0-100)."""
    result = await db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.owner_id == current_user.id,
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    data_result = await db.execute(
        select(PortalFetchedData).where(
            PortalFetchedData.client_id == client_id,
            PortalFetchedData.portal_type == PortalType.INCOME_TAX,
            PortalFetchedData.financial_year == financial_year,
        )
    )
    records = data_result.scalars().all()
    fetched = {r.data_type.lower(): json.loads(r.raw_data) for r in records if r.raw_data}

    ai = TaxAIAssistant()
    score = await ai.compute_audit_risk_score(
        client_data={"full_name": client.full_name, "pan": client.pan},
        itr_data={"financial_year": financial_year},
        ais_data=fetched.get("ais", {}),
    )
    return score


@router.post("/optimize-deductions")
async def optimize_deductions(
    req: DeductionOptimizerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find all deductions client can claim to minimize tax."""
    result = await db.execute(
        select(Client).where(
            Client.id == req.client_id,
            Client.owner_id == current_user.id,
        )
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    ai = TaxAIAssistant()
    analysis = await ai.optimize_deductions(
        client_name=client.full_name,
        financial_year=req.financial_year,
        gross_income=req.gross_income,
        current_deductions=req.current_deductions,
    )
    return {"analysis": analysis}
