"""Status Router - Request status and history endpoints."""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from backend.models.database import get_db, PendingRequest, AuditLog, RequestStatusEnum
from backend.models.schemas import RequestResponse, RequestStatus
from backend.services.audit_service import audit_service
from backend.services.rps_mock import rps_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/status", tags=["status"])


@router.get("/request/{request_id}", response_model=RequestResponse)
async def get_request_status(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the current status of a request.

    Returns full request details including AI verification results.
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


@router.get("/customer/{customer_id}")
async def get_customer_requests(
    customer_id: str,
    include_completed: bool = Query(True, description="Include completed requests"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get all requests for a specific customer.
    """
    query = db.query(PendingRequest).filter(
        PendingRequest.customer_id == customer_id
    )

    if not include_completed:
        query = query.filter(
            PendingRequest.status.notin_([
                RequestStatusEnum.APPROVED,
                RequestStatusEnum.REJECTED,
            ])
        )

    requests = query.order_by(PendingRequest.created_at.desc()).limit(limit).all()

    return {
        "customer_id": customer_id,
        "requests": [
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
        "total": len(requests),
    }


@router.get("/audit/{request_id}")
async def get_request_audit_trail(
    request_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the complete audit trail for a request.

    Returns all logged events in chronological order.
    """
    # Verify request exists
    request = db.query(PendingRequest).filter(
        PendingRequest.request_id == request_id
    ).first()

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    # Get audit entries
    audit_entries = audit_service.get_request_history(request_id)

    return {
        "request_id": request_id,
        "audit_trail": audit_entries,
        "total_events": len(audit_entries),
    }


@router.get("/all")
async def get_all_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all requests with optional status filter.
    """
    query = db.query(PendingRequest)

    if status:
        try:
            status_enum = RequestStatusEnum(status)
            query = query.filter(PendingRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    total = query.count()
    requests = query.order_by(PendingRequest.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "requests": [
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
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/rps/customer/{customer_id}")
async def get_rps_customer_info(
    customer_id: str,
):
    """
    Get customer information from RPS (mock core banking).

    Useful for verifying current customer state.
    """
    customer = rps_service.get_customer(customer_id)

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found in RPS")

    return customer


@router.get("/rps/history/{customer_id}")
async def get_rps_change_history(
    customer_id: str,
):
    """
    Get name change history for a customer from RPS.
    """
    history = rps_service.get_change_history(customer_id)

    return {
        "customer_id": customer_id,
        "change_history": history,
        "total_changes": len(history),
    }
