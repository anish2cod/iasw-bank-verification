"""SQLAlchemy database models for IASW."""

import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, JSON, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import enum

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./iasw.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class RequestStatusEnum(str, enum.Enum):
    """Status enum for pending requests."""
    SUBMITTED = "SUBMITTED"
    VALIDATING = "VALIDATING"
    PROCESSING_DOCUMENTS = "PROCESSING_DOCUMENTS"
    SCORING = "SCORING"
    AI_VERIFIED_PENDING_HUMAN = "AI_VERIFIED_PENDING_HUMAN"
    AI_FLAGGED_PENDING_HUMAN = "AI_FLAGGED_PENDING_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class PendingRequest(Base):
    """Model for pending name change requests."""
    __tablename__ = "pending_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), unique=True, index=True, nullable=False)
    customer_id = Column(String(50), index=True, nullable=False)
    old_name = Column(String(200), nullable=False)
    new_name = Column(String(200), nullable=False)
    request_type = Column(String(50), default="LEGAL_NAME_CHANGE")

    # Document information
    document_path = Column(String(500))
    document_type = Column(String(100))

    # Status tracking
    status = Column(SQLEnum(RequestStatusEnum), default=RequestStatusEnum.SUBMITTED)

    # AI verification results
    ai_summary = Column(Text)
    ai_recommendation = Column(String(50))  # APPROVE, REJECT, MANUAL_REVIEW
    confidence_scores = Column(JSON)  # {"name_match": 0.97, "authenticity": 0.85, "forgery_check": "PASS"}
    extracted_fields = Column(JSON)  # Fields extracted from document

    # Validation errors stored separately so the UI can surface them prominently
    validation_errors = Column(JSON)   # {"errors": [...], "warnings": [...], "customer_exists": bool, ...}

    # HITL fields
    checker_id = Column(String(50))
    checker_notes = Column(Text)
    approval_token = Column(String(100))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

    def __repr__(self):
        return f"<PendingRequest {self.request_id}: {self.old_name} -> {self.new_name}>"


class AuditLog(Base):
    """Audit log for all system actions."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), index=True)
    action = Column(String(100), nullable=False)
    actor = Column(String(100))  # System, AI Agent, Checker ID
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.actor}>"


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables and run lightweight migrations."""
    Base.metadata.create_all(bind=engine)
    # Add columns introduced after initial schema (SQLite ALTER TABLE is limited)
    from sqlalchemy import text
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE pending_requests ADD COLUMN validation_errors JSON",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists
