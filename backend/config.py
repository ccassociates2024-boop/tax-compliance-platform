from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TaxCompliance AI Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/taxdb_demo"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Credential Vault (AES-256)
    VAULT_MASTER_KEY: str          # 32-byte hex key for AES-256
    VAULT_SALT: str                # Per-deployment salt

    # Demo / Sandbox mode
    DEMO_MODE: bool = False          # Set True to enable demo sandbox (no real portals/payments)
    DEMO_USER_EMAIL: str = "demo@taxcomplianceai.in"
    DEMO_USER_PASSWORD: str = "demo123"

    # AI
    ANTHROPIC_API_KEY: str = ""      # Optional in demo mode
    AI_MODEL: str = "claude-sonnet-4-6"

    # AWS (Mumbai region for Indian data residency)
    AWS_ACCESS_KEY_ID: str = ""      # Optional in demo mode
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    S3_BUCKET_DOCUMENTS: str = "taxcompliance-docs-india"

    # Celery (optional — not needed in demo mode)
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Portal URLs
    IT_PORTAL_URL: str = "https://www.incometax.gov.in/iec/foportal/"
    TRACES_URL: str = "https://www.tdscpc.gov.in/app/login.xhtml"
    GST_PORTAL_URL: str = "https://services.gst.gov.in/services/login"

    # Razorpay
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
