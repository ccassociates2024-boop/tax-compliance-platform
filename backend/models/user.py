from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from database import Base
from db_types import GUID


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"     # Platform owner
    CA_FIRM = "ca_firm"             # CA / CS / Tax Consultant firm
    CA_STAFF = "ca_staff"           # Staff under a CA firm
    BUSINESS_OWNER = "business_owner"  # Direct small business user


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"         # Up to 50 clients
    PROFESSIONAL = "professional"  # Up to 500 clients
    ENTERPRISE = "enterprise"   # Unlimited


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(15), unique=True, nullable=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CA_FIRM)
    subscription_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)

    # CA / Firm specific
    firm_name = Column(String(255), nullable=True)
    membership_number = Column(String(50), nullable=True)   # ICAI/ICSI number
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)

    # Account state
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    two_fa_enabled = Column(Boolean, default=False)
    two_fa_secret = Column(String(100), nullable=True)

    # Subscription / Billing
    subscription_status = Column(String(50), default="active")     # active / cancelled / payment_failed
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    razorpay_subscription_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    clients = relationship("Client", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
