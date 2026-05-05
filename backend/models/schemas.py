"""Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class RequestStatus(str, Enum):
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


class RequestCreate(BaseModel):
    """Schema for creating a new name change request."""
    customer_id: str = Field(..., min_length=1, max_length=50, description="Customer ID")
    old_name: str = Field(..., min_length=1, max_length=200, description="Current legal name")
    new_name: str = Field(..., min_length=1, max_length=200, description="New legal name")
    request_type: str = Field(default="LEGAL_NAME_CHANGE", description="Type of request")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": "C001",
                "old_name": "Priya Sharma",
                "new_name": "Priya Mehta",
                "request_type": "LEGAL_NAME_CHANGE"
            }
        }


class ConfidenceScore(BaseModel):
    """Confidence scores from AI verification."""
    name_match: float = Field(..., ge=0, le=1, description="Name matching confidence")
    authenticity: float = Field(..., ge=0, le=1, description="Document authenticity score")
    forgery_check: str = Field(..., description="Forgery detection result: PASS/FAIL/UNCERTAIN")
    overall: float = Field(..., ge=0, le=1, description="Overall confidence score")


class ExtractedFields(BaseModel):
    """Fields extracted from document."""
    bride_name: Optional[str] = None
    groom_name: Optional[str] = None
    married_name: Optional[str] = None
    marriage_date: Optional[str] = None
    registration_number: Optional[str] = None
    raw_text: Optional[str] = None


class AIVerificationResult(BaseModel):
    """Result of AI verification pipeline."""
    summary: str = Field(..., description="Human-readable summary")
    recommendation: str = Field(..., description="APPROVE, REJECT, or MANUAL_REVIEW")
    confidence_scores: ConfidenceScore
    extracted_fields: Dict[str, Any]
    processing_time_ms: int


class RequestResponse(BaseModel):
    """Schema for request response."""
    request_id: str
    customer_id: str
    old_name: str
    new_name: str
    request_type: str
    document_path: Optional[str] = None
    status: RequestStatus
    ai_summary: Optional[str] = None
    ai_recommendation: Optional[str] = None
    confidence_scores: Optional[Dict[str, Any]] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    validation_errors: Optional[Dict[str, Any]] = None
    checker_id: Optional[str] = None
    checker_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CheckerAction(BaseModel):
    """Schema for checker approval/rejection."""
    action: str = Field(..., pattern="^(APPROVE|REJECT)$", description="APPROVE or REJECT")
    checker_id: str = Field(..., min_length=1, description="Checker's ID")
    notes: Optional[str] = Field(None, description="Optional notes")


class ApprovalToken(BaseModel):
    """Approval token for RPS gateway."""
    token: str
    request_id: str
    checker_id: str
    action: str
    issued_at: datetime
    expires_at: datetime


class RPSUpdateRequest(BaseModel):
    """Request to update RPS (mock core banking)."""
    customer_id: str
    new_name: str
    approval_token: str


class RPSCustomer(BaseModel):
    """Customer record in RPS mock."""
    customer_id: str
    name: str
    date_of_birth: Optional[str] = None
    address: Optional[str] = None
    account_status: str = "ACTIVE"


class RequestListResponse(BaseModel):
    """List of requests for checker dashboard."""
    requests: List[RequestResponse]
    total: int
    pending_review: int


class StatusUpdateRequest(BaseModel):
    """Internal status update request."""
    status: RequestStatus
    ai_summary: Optional[str] = None
    ai_recommendation: Optional[str] = None
    confidence_scores: Optional[Dict[str, Any]] = None
    extracted_fields: Optional[Dict[str, Any]] = None
