"""
Demo DB seeder — runs once on startup when DEMO_MODE=True.
Creates the demo CA account and 5 realistic demo clients.
Idempotent: safe to call multiple times (checks existence first).
"""
from __future__ import annotations
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from models import User, UserRole, SubscriptionPlan
from models.client import Client, ClientType
from .mock_data import DEMO_CLIENTS

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEMO_EMAIL = "demo@taxcomplianceai.in"
DEMO_PASSWORD = "demo123"


async def seed_demo_data(db: AsyncSession) -> None:
    """Seed demo account + 5 clients. Idempotent."""

    # ── 1. Demo user ──────────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    demo_user = result.scalar_one_or_none()

    if not demo_user:
        demo_user = User(
            email=DEMO_EMAIL,
            hashed_password=pwd_context.hash(DEMO_PASSWORD),
            full_name="C.A. Sourabh Bhimrao Chavan (Demo)",
            firm_name="C C & Associates — DEMO",
            role=UserRole.CA_FIRM,
            subscription_plan=SubscriptionPlan.PROFESSIONAL,
            subscription_status="active",
            is_active=True,
            is_verified=True,
            membership_number="ICAI-DM-2024",
        )
        db.add(demo_user)
        await db.flush()
        logger.info(f"✅ Demo user created: {DEMO_EMAIL}")
    else:
        logger.info(f"ℹ️  Demo user already exists: {DEMO_EMAIL}")

    # ── 2. Demo clients ───────────────────────────────────────────────────────
    existing_pans = set()
    existing_result = await db.execute(
        select(Client.pan).where(Client.owner_id == demo_user.id)
    )
    for row in existing_result.fetchall():
        existing_pans.add(row[0])

    _client_type_map = {
        "individual": ClientType.INDIVIDUAL,
        "company": ClientType.COMPANY,
        "huf": ClientType.HUF,
        "firm": ClientType.FIRM,
        "llp": ClientType.LLP,
    }

    created = 0
    for c in DEMO_CLIENTS:
        if c["pan"] in existing_pans:
            continue
        client = Client(
            owner_id=demo_user.id,
            full_name=c["full_name"],
            pan=c["pan"],
            client_type=_client_type_map.get(c["client_type"], ClientType.INDIVIDUAL),
            email=c.get("email"),
            phone=c.get("phone"),
            state_code=c.get("state_code"),
            gstin=c.get("gstin"),
            gst_registered=c.get("gst_registered", False),
            composition_scheme=c.get("composition_scheme", False),
            tan=c.get("tan"),
            is_tds_deductor=c.get("is_tds_deductor", False),
            current_fy=c.get("current_fy", "2024-25"),
            tags=c.get("tags", []),
            internal_notes=c.get("internal_notes"),
            is_active=True,
        )
        db.add(client)
        created += 1

    await db.commit()
    if created:
        logger.info(f"✅ {created} demo client(s) seeded")
    else:
        logger.info("ℹ️  All demo clients already exist")

    logger.info(
        "🎭 Demo mode ready — login: demo@taxcomplianceai.in / demo123"
    )
