from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from database import Base
from db_types import GUID


class PortalType(str, enum.Enum):
    INCOME_TAX = "income_tax"   # incometax.gov.in
    TRACES = "traces"           # tdscpc.gov.in
    GST = "gst"                 # gst.gov.in
    MCA = "mca"                 # mca.gov.in
    EPFO = "epfo"               # epfindia.gov.in


class PortalCredential(Base):
    """
    Stores encrypted portal credentials.
    Encryption: AES-256-GCM via credential_vault service.
    The plaintext password is NEVER stored — only the ciphertext + nonce + tag.
    """
    __tablename__ = "portal_credentials"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    portal_type = Column(Enum(PortalType), nullable=False)

    # Username is stored as-is (PAN / GSTIN — not secret)
    username = Column(String(50), nullable=False)

    # AES-256-GCM encrypted fields — stored as hex strings
    encrypted_password = Column(String(512), nullable=False)  # ciphertext hex
    nonce = Column(String(64), nullable=False)                 # 12-byte GCM nonce hex
    auth_tag = Column(String(64), nullable=False)              # 16-byte GCM tag hex

    # Session management (never stored long-term; cleared after use)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_success = Column(Boolean, nullable=True)
    session_active = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="credentials")


class PortalFetchedData(Base):
    """Stores raw data fetched from portals after automation run."""
    __tablename__ = "portal_fetched_data"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    portal_type = Column(Enum(PortalType), nullable=False)
    financial_year = Column(String(7), nullable=False)

    # The actual data (JSON)
    data_type = Column(String(50), nullable=False)   # "AIS", "26AS", "TDS_CERT", "GSTR2B", etc.
    raw_data = Column(String, nullable=True)          # JSON string of fetched data
    s3_key = Column(String(512), nullable=True)       # For large files (PDFs/Excel) stored in S3

    fetch_status = Column(String(20), default="pending")  # pending, success, failed
    error_message = Column(String(1000), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    client = relationship("Client", back_populates="fetched_data")
