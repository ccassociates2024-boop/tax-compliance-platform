"""
Subscription & Billing API
Endpoints: plans, checkout, verify payment, webhook, cancel, portal.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import Optional
import json, logging

from database import get_db
from api.auth import get_current_user
from models import User
from services.subscription import (
    PLANS, get_plan, get_razorpay, plan_allows, handle_webhook_event, RazorpayService
)
from config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()


# ─── PLAN CATALOG ─────────────────────────────────────────────────────────────

@router.get("/plans")
async def list_plans():
    """Public endpoint — no auth required."""
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "price_monthly_inr": plan.price_monthly / 100,
            "price_annual_inr": plan.price_annual / 100,
            "price_annual_per_month_inr": round(plan.price_annual / 100 / 12, 0),
            "annual_saving_pct": round(
                (1 - (plan.price_annual / (plan.price_monthly * 12))) * 100
            ) if plan.price_monthly > 0 else 0,
            "clients_limit": plan.clients_limit,
            "ai_queries_per_month": plan.ai_queries_per_month,
            "portal_fetches_per_month": plan.portal_fetches_per_month,
            "features": plan.features,
            "is_popular": plan.id == "professional",
            "is_custom": plan.id == "enterprise",
        }
        for plan in PLANS.values()
    ]


@router.get("/my-subscription")
async def my_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan = get_plan(current_user.subscription_plan or "free")
    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "status": current_user.subscription_status or "active",
        "expires_at": current_user.subscription_expires_at,
        "clients_limit": plan.clients_limit,
        "ai_queries_per_month": plan.ai_queries_per_month,
        "portal_fetches_per_month": plan.portal_fetches_per_month,
        "features": plan.features,
        "razorpay_subscription_id": getattr(current_user, 'razorpay_subscription_id', None),
    }


# ─── CHECKOUT ─────────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan_id: str
    billing: str = "monthly"   # monthly / annual


@router.post("/create-order")
async def create_order(
    req: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Razorpay order for the selected plan."""
    plan = get_plan(req.plan_id)
    if plan.id == "free":
        raise HTTPException(status_code=400, detail="Free plan does not require payment.")
    if plan.id == "enterprise":
        raise HTTPException(status_code=400, detail="Enterprise pricing is custom — contact sales@taxcomplianceai.in")

    amount = plan.price_annual if req.billing == "annual" else plan.price_monthly
    if amount == 0:
        raise HTTPException(status_code=400, detail="Invalid plan pricing configuration.")

    rzp = get_razorpay()
    order = rzp.create_order(
        amount_paise=amount,
        plan_id=req.plan_id,
        user_id=str(current_user.id),
        billing=req.billing,
    )

    return {
        "order_id": order["id"],
        "amount": order["amount"],
        "currency": order["currency"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "plan_name": plan.name,
        "billing": req.billing,
        "prefill": {
            "name": current_user.name,
            "email": current_user.email,
        },
    }


class CreateSubscriptionRequest(BaseModel):
    plan_id: str
    billing: str = "monthly"


@router.post("/create-subscription")
async def create_subscription(
    req: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Razorpay recurring subscription."""
    plan = get_plan(req.plan_id)
    rzp_plan_id = plan.razorpay_plan_id_annual if req.billing == "annual" else plan.razorpay_plan_id_monthly
    if not rzp_plan_id:
        raise HTTPException(status_code=400, detail="Subscription plan ID not configured.")

    rzp = get_razorpay()
    total_count = 12 if req.billing == "monthly" else 1
    sub = rzp.create_subscription(
        razorpay_plan_id=rzp_plan_id,
        total_count=total_count,
        notes={"user_id": str(current_user.id), "plan_id": req.plan_id},
    )
    return {
        "subscription_id": sub["id"],
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "plan_name": plan.name,
    }


# ─── PAYMENT VERIFICATION ─────────────────────────────────────────────────────

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan_id: str
    billing: str = "monthly"


@router.post("/verify-payment")
async def verify_payment(
    req: VerifyPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify Razorpay signature and activate subscription."""
    rzp = get_razorpay()
    valid = rzp.verify_payment_signature(
        req.razorpay_order_id,
        req.razorpay_payment_id,
        req.razorpay_signature,
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")

    from datetime import datetime, timedelta
    plan = get_plan(req.plan_id)
    expires_at = datetime.utcnow() + (
        timedelta(days=365) if req.billing == "annual" else timedelta(days=31)
    )

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(
            subscription_plan=req.plan_id,
            subscription_status="active",
            subscription_expires_at=expires_at,
            razorpay_payment_id=req.razorpay_payment_id,
        )
    )
    await db.commit()

    return {
        "success": True,
        "plan": plan.name,
        "expires_at": expires_at.isoformat(),
        "message": f"🎉 Welcome to {plan.name}! Your subscription is now active.",
    }


# ─── WEBHOOK ──────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_razorpay_signature: Optional[str] = Header(None),
):
    """
    Razorpay webhook endpoint.
    Configure in Razorpay Dashboard → Webhooks → https://api.taxcomplianceai.in/api/v1/subscriptions/webhook
    """
    body = await request.body()

    if x_razorpay_signature:
        rzp = get_razorpay()
        if not rzp.verify_webhook_signature(body, x_razorpay_signature):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event", "")
    logger.info(f"Razorpay webhook: {event}")

    result = await handle_webhook_event(event, payload.get("payload", {}), db)
    return {"received": True, "result": result}


# ─── SUBSCRIPTION MANAGEMENT ──────────────────────────────────────────────────

@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel subscription at end of current billing cycle."""
    sub_id = getattr(current_user, 'razorpay_subscription_id', None)
    if sub_id:
        rzp = get_razorpay()
        rzp.cancel_subscription(sub_id, cancel_at_cycle_end=True)

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(subscription_status="cancelled")
    )
    await db.commit()

    return {
        "success": True,
        "message": "Subscription cancelled. Access continues until end of billing period.",
    }


@router.post("/downgrade-free")
async def downgrade_to_free(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Immediately downgrade to free plan."""
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(subscription_plan="free", subscription_status="active", subscription_expires_at=None)
    )
    await db.commit()
    return {"success": True, "plan": "free"}


@router.get("/usage")
async def get_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current month's usage stats for the user."""
    from sqlalchemy import func
    from models import Client, AuditLog
    from datetime import datetime

    plan = get_plan(current_user.subscription_plan or "free")
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)

    # Client count
    client_count_result = await db.execute(
        select(func.count()).where(
            Client.owner_id == current_user.id,
            Client.is_active == True,
        )
    )
    client_count = client_count_result.scalar() or 0

    return {
        "plan": plan.id,
        "clients": {
            "used": client_count,
            "limit": plan.clients_limit,
            "pct": round(client_count / plan.clients_limit * 100) if plan.clients_limit > 0 else 0,
        },
        "ai_queries": {
            "used": 0,     # Would query AuditLog in production
            "limit": plan.ai_queries_per_month,
        },
        "portal_fetches": {
            "used": 0,     # Would query PortalFetchedData in production
            "limit": plan.portal_fetches_per_month,
        },
    }
