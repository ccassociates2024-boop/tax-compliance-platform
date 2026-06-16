from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, JSON, Text, Date, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from database import Base
from db_types import GUID


class ClientType(str, enum.Enum):
    INDIVIDUAL = "individual"
    HUF = "huf"
    FIRM = "firm"
    COMPANY = "company"
    LLP = "llp"
    TRUST = "trust"
    AOP = "aop"


class FilingStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    FILED = "filed"
    REJECTED = "rejected"


class Client(Base):
    __tablename__ = "clients"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    owner_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Identity
    full_name = Column(String(255), nullable=False)
    pan = Column(String(10), nullable=False, index=True)
    aadhaar_last4 = Column(String(4), nullable=True)   # Only last 4 digits for reference
    dob = Column(Date, nullable=True)
    client_type = Column(Enum(ClientType), nullable=False, default=ClientType.INDIVIDUAL)

    # Contact
    email = Column(String(255), nullable=True)
    phone = Column(String(15), nullable=True)
    address = Column(Text, nullable=True)
    state_code = Column(String(2), nullable=True)

    # GST
    gstin = Column(String(15), nullable=True, index=True)
    gst_registered = Column(Boolean, default=False)
    composition_scheme = Column(Boolean, default=False)

    # TAN (for TDS deductors)
    tan = Column(String(10), nullable=True, index=True)
    is_tds_deductor = Column(Boolean, default=False)

    # Financial Year settings
    current_fy = Column(String(7), default="2024-25")   # e.g. "2024-25"
    itr_form_type = Column(String(10), nullable=True)   # ITR-1, ITR-2, ITR-3, ITR-4

    # Status flags
    is_active = Column(Boolean, default=True)
    auto_fetch_enabled = Column(Boolean, default=False)  # Auto-fetch from portals

    # Tags / notes
    tags = Column(JSON, default=list)
    internal_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="clients")
    credentials = relationship("PortalCredential", back_populates="client", cascade="all, delete-orphan")
    itr_filings = relationship("ITRFiling", back_populates="client", cascade="all, delete-orphan")
    gst_filings = relationship("GSTFiling", back_populates="client", cascade="all, delete-orphan")
    tds_filings = relationship("TDSFiling", back_populates="client", cascade="all, delete-orphan")
    fetched_data = relationship("PortalFetchedData", back_populates="client", cascade="all, delete-orphan")
