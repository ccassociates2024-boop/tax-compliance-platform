"""
Subscription Plans & Razorpay Integration
Handles plan definitions, order creation, payment verification, webhooks, and enforcement.
"""
import hmac
import hashlib
import json
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

import razorpay
from fastapi import HTTPException

from config import get_settings

settings = get_settings()


# ─── PLAN DEFINITIONS ─────────────────────────────────────────────────────────

@dataclass
class Plan:
    id: str
    name: str
    price_monthly: int      # In paise (1 INR = 100 paise)
    price_annual: int
    clients_limit: int      # -1 = unlimited
    ai_queries_per_month: int
    portal_fetches_per_month: int
    features: list[str]
    razorpay_plan_id_monthly: str = ""
    razorpay_plan_id_annual: str = ""


PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_monthly=0,
        price_annual=0,
        clients_limit=3,
        ai_queries_per_month=20,
        portal_fetches_per_month=10,
        features=[
            "Up to 3 clients",
            "20 AI queries/month",
            "Income Tax computation",
            "Basic GST reports",
            "Community support",
        ],
    ),
    "starter": Plan(
        id="starter",
        name="Starter",
        price_monthly=99900,        # ₹999/month
        price_annual=899900,        # ₹8,999/year (~25% off)
        clients_limit=25,
        ai_queries_per_month=200,
        portal_fetches_per_month=100,
        features=[
            "Up to 25 clients",
            "200 AI queries/month",
            "Income Tax + GST + TDS modules",
            "Portal automation (IT, TRACES, GST)",
            "ITC reconciliation",
            "Excel import/export",
            "Email support",
        ],
        razorpay_plan_id_monthly="plan_starter_monthly",
        razorpay_plan_id_annual="plan_starter_annual",
    ),
    "professional": Plan(
        id="professional",
        name="Professional",
        price_monthly=249900,       # ₹2,499/month
        price_annual=2249900,       # ₹22,499/year
        clients_limit=150,
        ai_queries_per_month=1000,
        portal_fetches_per_month=500,
        features=[
            "Up to 150 clients",
            "1,000 AI queries/month",
            "All modules — IT, GST, TDS, Audit",
            "Full portal automation",
            "Bulk operations",
            "Custom AI prompts",
            "Whitelabel reports",
            "Priority support + onboarding call",
        ],
        razorpay_plan_id_monthly="plan_pro_monthly",
        razorpay_plan_id_annual="plan_pro_annual",
    ),
    "enterprise": Plan(
        id="enterprise",
        name="Enterprise",
        price_monthly=0,            # Custom pricing
        price_annual=0,
        clients_limit=-1,
        ai_queries_per_month=-1,
        portal_fetches_per_month=-1,
        features=[
            "Unlimited clients",
            "Unlimited AI queries",
            "All Professional features",
            "Dedicated server / on-prem option",
            "Custom integrations (ERP, Tally, SAP)",
            "SLA agreement",
            "Dedicated account manager",
            "24×7 phone support",
        ],
    ),
}

PLAN_HIERARCHY = ["free", "starter", "professional", "enterprise"]


def get_plan(plan_id: str) -> Plan:
    plan = PLANS.get(plan_id)
    if not plan:
        raise ValueError(f"Unknown plan: {plan_id}")
    return plan


def plan_allows(plan_id: str, feature: str, current_count: int = 0) -> bool:
    """Check if a plan allows a feature given current usage."""
    plan = get_plan(plan_id)

    if feature == "clients":
        return plan.clients_limit == -1 or current_count < plan.clients_limit
    if feature == "ai_query":
        return plan.ai_queries_per_month == -1 or current_count < plan.ai_queries_per_month
    if feature == "portal_fetch":
        return plan.portal_fetches_per_month == -1 or current_count < plan.portal_fetches_per_month
    if feature == "portal_automation":
        return plan_id in ("starter", "professional", "enterprise")
    if feature == "bulk_operations":
        return plan_id in ("professional", "enterprise")
    if feature == "whitelabel":
        return plan_id in ("professional", "enterprise")
    return True


# ─── RAZORPAY SERVICE ─────────────────────────────────────────────────────────

class RazorpayService:
    def __init__(self):
        self.client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

    def create_order(self, amount_paise: int, currency: str = "INR",
                     plan_id: str = "", user_id: str = "",
                     billing: str = "monthly") -> dict:
        """Create a Razorpay order for one-time or subscription payment."""
        notes = {
            "plan_id": plan_id,
            "user_id": user_id,
            "billing": billing,
        }
        order = self.client.order.create({
            "amount": amount_paise,
            "currency": currency,
            "notes": notes,
            "receipt": f"receipt_{user_id}_{plan_id}_{billing}",
        })
        return order

    def create_subscription(self, razorpay_plan_id: str, total_count: int = 12,
                            customer_notify: int = 1, notes: dict = None) -> dict:
        """Create a recurring subscription via Razorpay Subscriptions API."""
        payload = {
            "plan_id": razorpay_plan_id,
            "total_count": total_count,
            "customer_notify": customer_notify,
            "notes": notes or {},
        }
        return self.client.subscription.create(payload)

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify Razorpay payment signature — MUST be done before granting access."""
        body = f"{order_id}|{payment_id}"
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        """Verify Razorpay webhook signature using webhook secret."""
        expected = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def fetch_payment(self, payment_id: str) -> dict:
        return self.client.payment.fetch(payment_id)

    def fetch_subscription(self, subscription_id: str) -> dict:
        return self.client.subscription.fetch(subscription_id)

    def cancel_subscription(self, subscription_id: str, cancel_at_cycle_end: bool = True) -> dict:
        return self.client.subscription.cancel(
            subscription_id,
            {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0}
        )


def get_razorpay() -> RazorpayService:
    return RazorpayService()


# ─── SUBSCRIPTION EVENTS (webhook dispatch) ───────────────────────────────────

async def handle_webhook_event(event: str, payload: dict, db) -> dict:
    """
    Process Razorpay webhook events and update subscription status.
    Called by the webhook endpoint after signature verification.
    """
    from sqlalchemy import select, update
    from models import User

    if event == "payment.captured":
        payment = payload.get("payment", {}).get("entity", {})
        notes = payment.get("notes", {})
        user_id = notes.get("user_id")
        plan_id = notes.get("plan_id", "starter")
        billing = notes.get("billing", "monthly")

        if user_id:
            plan = get_plan(plan_id)
            expires_at = datetime.utcnow() + (
                timedelta(days=365) if billing == "annual" else timedelta(days=31)
            )
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    subscription_plan=plan_id,
                    subscription_status="active",
                    subscription_expires_at=expires_at,
                    razorpay_payment_id=payment.get("id"),
                )
            )
            await db.commit()
        return {"status": "updated", "plan": plan_id}

    elif event == "subscription.activated":
        sub = payload.get("subscription", {}).get("entity", {})
        notes = sub.get("notes", {})
        user_id = notes.get("user_id")
        plan_id = notes.get("plan_id", "starter")
        if user_id:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    subscription_plan=plan_id,
                    subscription_status="active",
                    razorpay_subscription_id=sub.get("id"),
                )
            )
            await db.commit()
        return {"status": "activated"}

    elif event in ("subscription.halted", "subscription.cancelled"):
        sub = payload.get("subscription", {}).get("entity", {})
        notes = sub.get("notes", {})
        user_id = notes.get("user_id")
        if user_id:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(subscription_status="cancelled", subscription_plan="free")
            )
            await db.commit()
        return {"status": "cancelled"}

    elif event == "payment.failed":
        payment = payload.get("payment", {}).get("entity", {})
        notes = payment.get("notes", {})
        user_id = notes.get("user_id")
        if user_id:
            await db.execute(
                update(User)
                .where(User.id == user_id)
                .values(subscription_status="payment_failed")
            )
            await db.commit()
        return {"status": "payment_failed"}

    return {"status": "ignored", "event": event}
