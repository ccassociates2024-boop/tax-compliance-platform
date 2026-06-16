"""
TaxCompliance AI Platform — FastAPI Application Entry Point
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import logging

from config import get_settings
from database import init_db, AsyncSessionLocal
from api import auth, clients, income_tax, gst, tds, ai_engine, gst_data, subscriptions, demo as demo_api

settings = get_settings()
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME + (" [DEMO]" if settings.DEMO_MODE else ""),
    version=settings.APP_VERSION,
    docs_url="/api/docs" if (settings.DEBUG or settings.DEMO_MODE) else None,
    redoc_url=None,
)

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.taxcomplianceai.in",
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",   # Vite default fallback port
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    # Render assigns a subdomain at deploy time we can't know in advance — allow any *.onrender.com origin
    allow_origin_regex=r"https://.*\.onrender\.com" if settings.DEMO_MODE else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.taxcomplianceai.in", "localhost", "127.0.0.1", "*"],
)

# ─── ROUTES ───────────────────────────────────────────────────────────────────

app.include_router(auth.router,        prefix="/api/v1/auth",        tags=["Authentication"])
app.include_router(clients.router,     prefix="/api/v1/clients",     tags=["Client Management"])
app.include_router(income_tax.router,  prefix="/api/v1/income-tax",  tags=["Income Tax"])
app.include_router(gst.router,         prefix="/api/v1/gst",         tags=["GST"])
app.include_router(tds.router,         prefix="/api/v1/tds",         tags=["TDS"])
app.include_router(ai_engine.router,   prefix="/api/v1/ai",          tags=["AI Engine"])
app.include_router(gst_data.router,    prefix="/api/v1/gst-data",    tags=["GST Data"])
app.include_router(subscriptions.router, prefix="/api/v1/subscriptions", tags=["Subscriptions & Billing"])

# Demo router — always registered so /demo/status works, but each endpoint guards itself
app.include_router(demo_api.router, prefix="/api/v1/demo", tags=["Demo Mode"])

# ─── EVENTS ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    logger.info(f"✅ {settings.APP_NAME} v{settings.APP_VERSION} started")

    if settings.DEMO_MODE:
        logger.info("🎭 DEMO MODE is ON — seeding demo data...")
        from demo.seed import seed_demo_data
        async with AsyncSessionLocal() as session:
            await seed_demo_data(session)
        logger.info("🎭 Demo seed complete — demo@taxcomplianceai.in / demo123")

@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
