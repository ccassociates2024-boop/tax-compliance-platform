from sqlalchemy import Column, String, Boolean, DateTime, Enum, ForeignKey, JSON, Numeric, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from database import Base
from db_types import GUID


class FilingStatus(str, enum.Enum):
    DRAFT = "draft"
    AI_REVIEW = "ai_review"
    CA_REVIEW = "ca_review"
    FILED = "filed"
    ACKNOWLEDGED = "acknowledged"
    DEFECTIVE = "defective"


# ─── INCOME TAX ─────────────────────────────────────────────────────────────

class ITRFiling(Base):
    __tablename__ = "itr_filings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    financial_year = Column(String(7), nullable=False)   # "2024-25"
    assessment_year = Column(String(7), nullable=False)  # "2025-26"
    itr_form = Column(String(10), nullable=False)        # ITR-1 to ITR-7

    status = Column(Enum(FilingStatus), default=FilingStatus.DRAFT)

    # Fetched data (from AIS, 26AS, Form 16)
    ais_data = Column(JSON, nullable=True)
    form26as_data = Column(JSON, nullable=True)
    tds_data = Column(JSON, nullable=True)
    advance_tax_data = Column(JSON, nullable=True)
    self_assessment_tax_data = Column(JSON, nullable=True)

    # Computed income heads
    salary_income = Column(Numeric(15, 2), default=0)
    house_property_income = Column(Numeric(15, 2), default=0)
    business_income = Column(Numeric(15, 2), default=0)
    capital_gains_stcg = Column(Numeric(15, 2), default=0)
    capital_gains_ltcg = Column(Numeric(15, 2), default=0)
    other_sources_income = Column(Numeric(15, 2), default=0)
    gross_total_income = Column(Numeric(15, 2), default=0)

    # Deductions
    deduction_80c = Column(Numeric(15, 2), default=0)
    deduction_80d = Column(Numeric(15, 2), default=0)
    deduction_80ccd1b = Column(Numeric(15, 2), default=0)
    deduction_hra = Column(Numeric(15, 2), default=0)
    deduction_24b = Column(Numeric(15, 2), default=0)   # Home loan interest
    other_deductions = Column(JSON, nullable=True)       # {section: amount}
    total_deductions = Column(Numeric(15, 2), default=0)

    # Tax computation
    total_taxable_income = Column(Numeric(15, 2), default=0)
    tax_at_normal_rates = Column(Numeric(15, 2), default=0)
    rebate_87a = Column(Numeric(15, 2), default=0)
    surcharge = Column(Numeric(15, 2), default=0)
    health_education_cess = Column(Numeric(15, 2), default=0)
    total_tax_liability = Column(Numeric(15, 2), default=0)
    tds_credit = Column(Numeric(15, 2), default=0)
    advance_tax_credit = Column(Numeric(15, 2), default=0)
    self_assessment_tax_paid = Column(Numeric(15, 2), default=0)
    tax_payable_refundable = Column(Numeric(15, 2), default=0)  # + payable, - refund

    # Regime
    tax_regime = Column(String(10), default="new")   # "old" or "new"
    regime_comparison = Column(JSON, nullable=True)  # AI-computed comparison

    # AI insights
    ai_suggestions = Column(JSON, nullable=True)
    ai_risk_score = Column(Integer, nullable=True)   # 0-100 audit risk score
    ai_notes = Column(Text, nullable=True)
    mismatch_flags = Column(JSON, nullable=True)     # AIS vs Form 16 mismatches

    # Filing details
    acknowledgement_number = Column(String(20), nullable=True)
    filed_at = Column(DateTime(timezone=True), nullable=True)
    verification_method = Column(String(20), nullable=True)  # "aadhaar_otp", "net_banking", "dsc"
    xml_s3_key = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="itr_filings")


# ─── TDS ─────────────────────────────────────────────────────────────────────

class TDSFiling(Base):
    __tablename__ = "tds_filings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    financial_year = Column(String(7), nullable=False)
    quarter = Column(String(2), nullable=False)   # Q1, Q2, Q3, Q4
    form_type = Column(String(10), nullable=False)  # 24Q, 26Q, 27Q, 27EQ

    status = Column(Enum(FilingStatus), default=FilingStatus.DRAFT)

    # Deductee data
    deductee_records = Column(JSON, nullable=True)  # List of deductions
    total_deductions_count = Column(Integer, default=0)
    total_tds_amount = Column(Numeric(15, 2), default=0)
    total_challan_amount = Column(Numeric(15, 2), default=0)
    short_deduction = Column(Numeric(15, 2), default=0)

    # Challans
    challans = Column(JSON, nullable=True)

    # TRACES data
    traces_status = Column(String(50), nullable=True)
    defaults_amount = Column(Numeric(15, 2), default=0)
    interest_u234e = Column(Numeric(15, 2), default=0)   # Late filing fee

    # Filing
    provisional_receipt_number = Column(String(50), nullable=True)
    filed_at = Column(DateTime(timezone=True), nullable=True)
    fvu_file_s3_key = Column(String(512), nullable=True)   # FVU validated file

    ai_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="tds_filings")


# ─── GST ─────────────────────────────────────────────────────────────────────

class GSTFiling(Base):
    __tablename__ = "gst_filings"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    client_id = Column(GUID(), ForeignKey("clients.id"), nullable=False)
    financial_year = Column(String(7), nullable=False)
    tax_period = Column(String(7), nullable=False)   # "042024" = April 2024
    return_type = Column(String(10), nullable=False)  # GSTR1, GSTR3B, GSTR9, etc.

    status = Column(Enum(FilingStatus), default=FilingStatus.DRAFT)

    # GSTR-1 data
    gstr1_b2b = Column(JSON, nullable=True)          # B2B invoices
    gstr1_b2c_large = Column(JSON, nullable=True)    # B2C large (> 2.5L inter-state)
    gstr1_b2c_small = Column(JSON, nullable=True)    # B2C small
    gstr1_cdnr = Column(JSON, nullable=True)         # Credit/Debit notes (registered)
    gstr1_cdnur = Column(JSON, nullable=True)        # Credit/Debit notes (unregistered)
    gstr1_exp = Column(JSON, nullable=True)          # Exports
    gstr1_hsn_summary = Column(JSON, nullable=True)  # HSN-wise summary
    gstr1_doc_summary = Column(JSON, nullable=True)  # Document summary

    # GSTR-3B data
    gstr3b_outward_taxable = Column(Numeric(15, 2), default=0)
    gstr3b_outward_exempt = Column(Numeric(15, 2), default=0)
    gstr3b_itc_available = Column(JSON, nullable=True)   # {igst, cgst, sgst, cess}
    gstr3b_itc_reversed = Column(JSON, nullable=True)
    gstr3b_net_itc = Column(JSON, nullable=True)
    gstr3b_tax_payable = Column(JSON, nullable=True)     # {igst, cgst, sgst, cess}
    gstr3b_tax_paid_itc = Column(JSON, nullable=True)
    gstr3b_tax_paid_cash = Column(JSON, nullable=True)
    gstr3b_interest = Column(Numeric(15, 2), default=0)
    gstr3b_late_fee = Column(Numeric(15, 2), default=0)

    # GSTR-2B reconciliation
    gstr2b_data = Column(JSON, nullable=True)
    reconciliation_result = Column(JSON, nullable=True)  # Matched/unmatched invoices
    itc_mismatch_amount = Column(Numeric(15, 2), default=0)

    # Filing
    arn = Column(String(30), nullable=True)              # Acknowledgement reference number
    filed_at = Column(DateTime(timezone=True), nullable=True)
    ai_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("Client", back_populates="gst_filings")


# ─── AUDIT LOG ───────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    client_id = Column(GUID(), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="audit_logs")
