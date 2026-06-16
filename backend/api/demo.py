"""
Demo API endpoints — only active when DEMO_MODE=True.

Endpoints:
  POST /demo/login          — one-click demo login (no password form)
  GET  /demo/clients        — list all 5 demo clients
  GET  /demo/itr/{pan}      — pre-computed ITR result
  GET  /demo/gst/{pan}      — pre-computed GST result
  GET  /demo/tds/{pan}      — pre-computed TDS result
  POST /demo/ai/chat        — canned AI responses (keyword-matched)
  POST /demo/payment/simulate — simulate a successful Razorpay payment
  GET  /demo/status         — confirm demo mode is active
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import get_settings
from database import get_db
from models import User, SubscriptionPlan
from api.auth import create_access_token, _user_payload, get_current_user

settings = get_settings()
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_EMAIL = "demo@taxcomplianceai.in"

# Guard: all demo routes abort immediately if demo mode is off
def _require_demo():
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled on this server.")


# ─── STATUS ───────────────────────────────────────────────────────────────────

@router.get("/status")
async def demo_status():
    _require_demo()
    return {
        "demo_mode": True,
        "message": "🎭 Demo mode is active. All data is simulated.",
        "demo_email": DEMO_EMAIL,
        "demo_password": settings.DEMO_USER_PASSWORD,
        "clients": 5,
        "features_disabled": [
            "Real portal fetch (Income Tax, GST, TRACES)",
            "Real Razorpay payments",
            "Real Anthropic AI calls (using canned responses)",
            "Email notifications",
            "AWS S3 document storage",
        ],
    }


# ─── DEMO LOGIN ───────────────────────────────────────────────────────────────

@router.post("/login")
async def demo_login(db: AsyncSession = Depends(get_db)):
    """One-click demo login — no form, no password entry needed."""
    _require_demo()

    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=503,
            detail="Demo user not seeded yet. Please restart the server.",
        )

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "role": user.role.value,
        "user": _user_payload(user).model_dump(),
        "demo_mode": True,
        "message": "Welcome to the demo! Explore with 5 pre-loaded clients.",
    }


# ─── DEMO CLIENTS ─────────────────────────────────────────────────────────────

@router.get("/clients")
async def demo_clients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns demo clients owned by the demo account."""
    _require_demo()
    from models.client import Client
    result = await db.execute(
        select(Client).where(Client.owner_id == current_user.id, Client.is_active == True)
    )
    clients = result.scalars().all()
    return {
        "demo_mode": True,
        "total": len(clients),
        "clients": [
            {
                "id": str(c.id),
                "full_name": c.full_name,
                "pan": c.pan,
                "client_type": c.client_type.value,
                "email": c.email,
                "gst_registered": c.gst_registered,
                "is_tds_deductor": c.is_tds_deductor,
                "tags": c.tags or [],
                "current_fy": c.current_fy,
            }
            for c in clients
        ],
    }


# ─── DEMO ITR ─────────────────────────────────────────────────────────────────

@router.get("/itr/{pan}")
async def demo_itr_result(pan: str, _: User = Depends(get_current_user)):
    """Returns pre-computed ITR result for a demo client."""
    _require_demo()
    from demo.mock_data import get_mock_itr_result
    data = get_mock_itr_result(pan)
    if not data:
        raise HTTPException(status_code=404, detail=f"No demo ITR data for PAN {pan}. Valid PANs: ABCPD1234R, BFXPJ5678S, AADCS3456M, CLHPP7890V, DFZPK2345P")
    return {"demo_mode": True, **data}


# ─── DEMO GST ─────────────────────────────────────────────────────────────────

@router.get("/gst/{pan}")
async def demo_gst_result(pan: str, _: User = Depends(get_current_user)):
    """Returns pre-computed GST result for a demo client."""
    _require_demo()
    from demo.mock_data import get_mock_gst_result
    data = get_mock_gst_result(pan)
    if not data:
        raise HTTPException(status_code=404, detail=f"No GST data for PAN {pan}. This client is not GST registered.")
    return {"demo_mode": True, **data}


# ─── DEMO TDS ─────────────────────────────────────────────────────────────────

@router.get("/tds/{pan}")
async def demo_tds_result(pan: str, _: User = Depends(get_current_user)):
    """Returns pre-computed TDS result for a demo client."""
    _require_demo()
    from demo.mock_data import get_mock_tds_result
    data = get_mock_tds_result(pan)
    if not data:
        raise HTTPException(status_code=404, detail=f"No TDS data for PAN {pan}.")
    return {"demo_mode": True, **data}


# ─── DEMO AI CHAT ─────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    client_id: str | None = None


@router.post("/ai/chat")
async def demo_ai_chat(req: ChatRequest, _: User = Depends(get_current_user)):
    """Canned AI responses — no Anthropic API call needed in demo."""
    _require_demo()
    from demo.mock_data import get_mock_ai_response

    last_user_message = ""
    for m in reversed(req.messages):
        if m.role == "user":
            last_user_message = m.content
            break

    response_text = get_mock_ai_response(last_user_message)

    # Stream character by character like real AI would
    async def _stream():
        yield f"data: {{}}\n\n"   # SSE start
        chunk_size = 8
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i : i + chunk_size]
            import json
            yield f"data: {json.dumps({'delta': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ─── DEMO PAYMENT SIMULATION ─────────────────────────────────────────────────

class PaymentSimRequest(BaseModel):
    plan: str = "professional"


@router.post("/payment/simulate")
async def demo_simulate_payment(
    req: PaymentSimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulate a successful Razorpay payment — upgrades demo user to selected plan."""
    _require_demo()

    plan_map = {
        "starter": SubscriptionPlan.STARTER,
        "professional": SubscriptionPlan.PROFESSIONAL,
        "enterprise": SubscriptionPlan.ENTERPRISE,
    }
    plan_enum = plan_map.get(req.plan.lower())
    if not plan_enum:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.plan}")

    current_user.subscription_plan = plan_enum
    current_user.subscription_status = "active"
    current_user.subscription_expires_at = datetime.utcnow() + timedelta(days=30)
    current_user.razorpay_payment_id = f"DEMO_PAY_{req.plan.upper()}_SIMULATED"
    await db.commit()

    plan_prices = {"starter": "₹999", "professional": "₹2,499", "enterprise": "Custom"}
    return {
        "demo_mode": True,
        "success": True,
        "plan": req.plan,
        "message": f"🎉 Demo: Payment of {plan_prices.get(req.plan, '–')} simulated successfully. Plan upgraded to {req.plan.title()}.",
        "payment_id": f"DEMO_PAY_{req.plan.upper()}_SIMULATED",
        "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
    }


# ─── DEMO PORTAL FETCH SIMULATION ────────────────────────────────────────────

@router.post("/portal/fetch/{pan}")
async def demo_portal_fetch(pan: str, _: User = Depends(get_current_user)):
    """Simulate fetching data from govt portals — returns mock portal data."""
    _require_demo()
    from demo.mock_data import get_mock_itr_result

    data = get_mock_itr_result(pan)
    if not data:
        raise HTTPException(status_code=404, detail=f"No demo data for PAN {pan}")

    form_26as = data.get("form_26as_summary", {})
    return {
        "demo_mode": True,
        "pan": pan.upper(),
        "client_name": data["client_name"],
        "portal_fetch_simulated": True,
        "fetched_at": datetime.utcnow().isoformat(),
        "income_tax_portal": {
            "status": "success",
            "form_26as": form_26as,
            "itr_status": "Not Filed" if data.get("itr_form") else "Filed",
            "outstanding_demand": 0,
        },
        "traces": {
            "status": "success",
            "tds_certificates_count": 1,
            "defaults": [],
        },
        "gst_portal": {
            "status": "success" if data.get("gst_summary") else "not_registered",
            "gstin": data.get("gst_summary", {}).get("gstin", "NOT REGISTERED"),
            "last_return_filed": "GSTR-3B for Feb 2025",
        },
        "note": "DEMO: In production, this triggers Playwright browser automation to log into actual portals.",
    }
