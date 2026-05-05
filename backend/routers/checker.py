"""Checker Router - Handles HITL approval workflow."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta

from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.database import get_db, PendingRequest, RequestStatusEnum
from backend.models.schemas import (
    RequestResponse,
    RequestStatus,
    CheckerAction,
    RequestListResponse,
)
from backend.services.rps_mock import rps_service
from backend.services.audit_service import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/checker", tags=["checker"])


@router.get("/pending", response_model=RequestListResponse)
async def get_pending_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    customer_id: Optional[str] = Query(None, description="Filter by customer"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get list of requests pending human review.

    Returns requests with status AI_VERIFIED_PENDING_HUMAN or AI_FLAGGED_PENDING_HUMAN.
    """
    query = db.query(PendingRequest)

    # Filter by pending human review statuses
    if status:
        try:
            status_enum = RequestStatusEnum(status)
            query = query.filter(PendingRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    else:
        # Default: show all pending human review
        query = query.filter(
            or_(
                PendingRequest.status == RequestStatusEnum.AI_VERIFIED_PENDING_HUMAN,
                PendingRequest.status == RequestStatusEnum.AI_FLAGGED_PENDING_HUMAN,
            )
        )

    if customer_id:
        query = query.filter(PendingRequest.customer_id == customer_id)

    # Get total count
    total = query.count()

    # Get pending review count
    pending_review = db.query(PendingRequest).filter(
        or_(
            PendingRequest.status == RequestStatusEnum.AI_VERIFIED_PENDING_HUMAN,
            PendingRequest.status == RequestStatusEnum.AI_FLAGGED_PENDING_HUMAN,
        )
    ).count()

    # Apply pagination and ordering
    requests = query.order_by(PendingRequest.created_at.desc()).offset(offset).limit(limit).all()

    return RequestListResponse(
        requests=[
            RequestResponse(
                request_id=r.request_id,
                customer_id=r.customer_id,
                old_name=r.old_name,
                new_name=r.new_name,
                request_type=r.request_type,
                document_path=r.document_path,
                status=RequestStatus(r.status.value),
                ai_summary=r.ai_summary,
                ai_recommendation=r.ai_recommendation,
                confidence_scores=r.confidence_scores,
                extracted_fields=r.extracted_fields,
                validation_errors=r.validation_errors,
                checker_id=r.checker_id,
                checker_notes=r.checker_notes,
                created_at=r.created_at,
                updated_at=r.updated_at,
                completed_at=r.completed_at,
            )
            for r in requests
        ],
        total=total,
        pending_review=pending_review,
    )


@router.get("/request/{request_id}", response_model=RequestResponse)
async def get_request_details(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific request.

    Includes AI summary, confidence scores, and extracted fields.
    """
    request = db.query(PendingRequest).filter(
        PendingRequest.request_id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return RequestResponse(
        request_id=request.request_id,
        customer_id=request.customer_id,
        old_name=request.old_name,
        new_name=request.new_name,
        request_type=request.request_type,
        document_path=request.document_path,
        status=RequestStatus(request.status.value),
        ai_summary=request.ai_summary,
        ai_recommendation=request.ai_recommendation,
        confidence_scores=request.confidence_scores,
        extracted_fields=request.extracted_fields,
        validation_errors=request.validation_errors,
        checker_id=request.checker_id,
        checker_notes=request.checker_notes,
        created_at=request.created_at,
        updated_at=request.updated_at,
        completed_at=request.completed_at,
    )


@router.post("/request/{request_id}/action", response_model=RequestResponse)
async def process_checker_action(
    request_id: str,
    action: CheckerAction,
    db: Session = Depends(get_db),
):
    """
    Process checker approval or rejection.

    - **action**: APPROVE or REJECT
    - **checker_id**: ID of the checker
    - **notes**: Optional notes explaining the decision

    For APPROVE:
    - Generates approval token
    - Updates RPS with new name
    - Status becomes APPROVED

    For REJECT:
    - Status becomes REJECTED
    - No RPS update
    """
    request = db.query(PendingRequest).filter(
        PendingRequest.request_id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Validate current status allows action
    allowed_statuses = [
        RequestStatusEnum.AI_VERIFIED_PENDING_HUMAN,
        RequestStatusEnum.AI_FLAGGED_PENDING_HUMAN,
    ]

    if request.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Request status {request.status.value} does not allow checker action"
        )

    logger.info(
        f"Checker: Processing {action.action} for {request_id} by {action.checker_id}"
    )

    # Log the checker action
    audit_service.log_checker_action(
        request_id=request_id,
        checker_id=action.checker_id,
        action=action.action,
        notes=action.notes,
    )

    if action.action == "APPROVE":
        # Generate approval token
        approval_token = rps_service.generate_approval_token()

        # Register token with RPS
        rps_service.register_approval_token(
            token=approval_token,
            request_id=request_id,
            checker_id=action.checker_id,
            customer_id=request.customer_id,
            new_name=request.new_name,
        )

        # Update RPS with new name
        rps_result = rps_service.update_customer_name(
            customer_id=request.customer_id,
            new_name=request.new_name,
            approval_token=approval_token,
        )

        if rps_result["success"]:
            request.status = RequestStatusEnum.APPROVED
            request.approval_token = approval_token[:8] + "..."  # Store partial for audit

            # Log successful RPS update
            audit_service.log_rps_update(
                request_id=request_id,
                customer_id=request.customer_id,
                old_name=request.old_name,
                new_name=request.new_name,
                success=True,
            )

            logger.info(f"Checker: Request {request_id} APPROVED, RPS updated")
        else:
            # RPS update failed
            audit_service.log_rps_update(
                request_id=request_id,
                customer_id=request.customer_id,
                old_name=request.old_name,
                new_name=request.new_name,
                success=False,
                error=rps_result.get("error"),
            )

            raise HTTPException(
                status_code=500,
                detail=f"RPS update failed: {rps_result.get('error')}"
            )

    else:  # REJECT
        request.status = RequestStatusEnum.REJECTED
        logger.info(f"Checker: Request {request_id} REJECTED")

    # Update checker info
    request.checker_id = action.checker_id
    request.checker_notes = action.notes
    request.completed_at = datetime.utcnow()
    request.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(request)

    return RequestResponse(
        request_id=request.request_id,
        customer_id=request.customer_id,
        old_name=request.old_name,
        new_name=request.new_name,
        request_type=request.request_type,
        document_path=request.document_path,
        status=RequestStatus(request.status.value),
        ai_summary=request.ai_summary,
        ai_recommendation=request.ai_recommendation,
        confidence_scores=request.confidence_scores,
        extracted_fields=request.extracted_fields,
        validation_errors=request.validation_errors,
        checker_id=request.checker_id,
        checker_notes=request.checker_notes,
        created_at=request.created_at,
        updated_at=request.updated_at,
        completed_at=request.completed_at,
    )


@router.get("/stats")
async def get_checker_stats(
    db: Session = Depends(get_db),
):
    """
    Get checker dashboard statistics.
    """
    total = db.query(PendingRequest).count()

    pending = db.query(PendingRequest).filter(
        or_(
            PendingRequest.status == RequestStatusEnum.AI_VERIFIED_PENDING_HUMAN,
            PendingRequest.status == RequestStatusEnum.AI_FLAGGED_PENDING_HUMAN,
        )
    ).count()

    approved = db.query(PendingRequest).filter(
        PendingRequest.status == RequestStatusEnum.APPROVED
    ).count()

    rejected = db.query(PendingRequest).filter(
        PendingRequest.status == RequestStatusEnum.REJECTED
    ).count()

    processing = db.query(PendingRequest).filter(
        PendingRequest.status.in_([
            RequestStatusEnum.SUBMITTED,
            RequestStatusEnum.VALIDATING,
            RequestStatusEnum.PROCESSING_DOCUMENTS,
            RequestStatusEnum.SCORING,
        ])
    ).count()

    errors = db.query(PendingRequest).filter(
        PendingRequest.status == RequestStatusEnum.ERROR
    ).count()

    # AI recommendations breakdown
    ai_approve = db.query(PendingRequest).filter(
        PendingRequest.ai_recommendation == "APPROVE"
    ).count()

    ai_reject = db.query(PendingRequest).filter(
        PendingRequest.ai_recommendation == "REJECT"
    ).count()

    ai_review = db.query(PendingRequest).filter(
        PendingRequest.ai_recommendation == "MANUAL_REVIEW"
    ).count()

    return {
        "total": total,
        "pending_review": pending,
        "approved": approved,
        "rejected": rejected,
        "processing": processing,
        "errors": errors,
        "ai_recommendations": {
            "approve": ai_approve,
            "reject": ai_reject,
            "manual_review": ai_review,
        }
    }


_MIME_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


@router.get("/document/{request_id}")
async def get_request_document(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Serve the uploaded supporting document for a request.
    Used by the checker UI to display the document image.
    """
    request = db.query(PendingRequest).filter(
        PendingRequest.request_id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    if not request.document_path:
        raise HTTPException(status_code=404, detail="No document attached to this request")

    doc_path = Path(request.document_path)
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on server")

    media_type = _MIME_MAP.get(doc_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(doc_path),
        media_type=media_type,
        filename=doc_path.name,
        content_disposition_type="inline",
    )
