"""Intake Router - Handles new request submissions."""

import uuid
import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from backend.models.database import get_db, PendingRequest, RequestStatusEnum
from backend.models.schemas import RequestCreate, RequestResponse, RequestStatus
from backend.services.filenet_mock import filenet_service
from backend.services.audit_service import audit_service
from backend.agents.orchestrator import run_workflow
from backend.config import REQUEST_ID_PREFIX, UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intake", tags=["intake"])


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return f"{REQUEST_ID_PREFIX}-{uuid.uuid4().hex[:8].upper()}"


async def process_request_async(
    request_id: str,
    customer_id: str,
    old_name: str,
    new_name: str,
    document_path: Optional[str],
    db_url: str,
):
    """Background task: runs the AI pipeline and writes intermediate status to DB."""
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    LocalSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _update_status(new_status: str):
        """Sync DB write called from async context via asyncio.to_thread."""
        db = LocalSession()
        try:
            req = db.query(PendingRequest).filter(
                PendingRequest.request_id == request_id
            ).first()
            if req:
                req.status = RequestStatusEnum(new_status)
                req.updated_at = datetime.utcnow()
                db.commit()
        except Exception as exc:
            logger.warning(f"Intermediate status update failed: {exc}")
        finally:
            db.close()

    async def status_callback(new_status: str):
        await asyncio.to_thread(_update_status, new_status)

    db = LocalSession()
    try:
        request = db.query(PendingRequest).filter(
            PendingRequest.request_id == request_id
        ).first()
        if not request:
            logger.error(f"Request {request_id} not found for processing")
            return

        # Run the full pipeline; callback updates DB at each stage
        result = await run_workflow(
            request_id=request_id,
            customer_id=customer_id,
            old_name=old_name,
            new_name=new_name,
            document_path=document_path,
            status_callback=status_callback,
        )

        # Re-fetch after pipeline (status may have been updated by callback)
        db.expire_all()
        request = db.query(PendingRequest).filter(
            PendingRequest.request_id == request_id
        ).first()

        # Final status
        request.status = RequestStatusEnum(result.get("status", "ERROR"))
        request.ai_recommendation = result.get("recommendation")

        # AI summary
        summary_result = result.get("summary_result") or {}
        request.ai_summary = summary_result.get("summary", "")

        # Confidence scores
        scoring = result.get("scoring_result") or {}
        if scoring:
            request.confidence_scores = {
                "name_match": scoring.get("name_match_score"),
                "authenticity": scoring.get("authenticity_score"),
                "forgery_check": scoring.get("forgery_check"),
                "overall": scoring.get("overall_score"),
                "details": scoring.get("details", {}),
            }

        # Extracted fields
        request.extracted_fields = result.get("extracted_fields") or {}

        # Validation errors — stored separately for prominent UI display
        validation = result.get("validation_result") or {}
        if validation:
            request.validation_errors = {
                "errors": validation.get("errors", []),
                "warnings": validation.get("warnings", []),
                "customer_exists": validation.get("customer_exists"),
                "name_matches": validation.get("name_matches"),
                "account_active": validation.get("account_active"),
            }

        request.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Request {request_id} complete: {request.status}")

    except Exception as e:
        logger.error(f"Error processing {request_id}: {e}", exc_info=True)
        try:
            db.rollback()
            req = db.query(PendingRequest).filter(
                PendingRequest.request_id == request_id
            ).first()
            if req:
                req.status = RequestStatusEnum.ERROR
                req.ai_summary = f"Processing error: {e}"
                req.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("/submit", response_model=RequestResponse)
async def submit_request(
    background_tasks: BackgroundTasks,
    customer_id: str = Form(...),
    old_name: str = Form(...),
    new_name: str = Form(...),
    request_type: str = Form(default="LEGAL_NAME_CHANGE"),
    document: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """
    Submit a new name change request.

    - **customer_id**: Customer ID (must exist in RPS)
    - **old_name**: Current legal name
    - **new_name**: New legal name to change to
    - **document**: Supporting document (PDF or image)
    """
    # Generate request ID
    request_id = generate_request_id()

    logger.info(f"Intake: New request {request_id} for customer {customer_id}")

    # Handle document upload
    document_path = None
    document_type = None

    if document:
        # Read file content
        content = await document.read()

        # Store in FileNet mock
        result = filenet_service.store_document(
            file_content=content,
            filename=document.filename,
            document_class="MARRIAGE_CERTIFICATE",
            metadata={"request_id": request_id, "customer_id": customer_id},
        )

        document_path = result["storage_path"]
        document_type = "MARRIAGE_CERTIFICATE"

        # Link document to request
        filenet_service.link_to_request(result["document_id"], request_id)

        logger.info(f"Intake: Document stored at {document_path}")

    # Create database record
    db_request = PendingRequest(
        request_id=request_id,
        customer_id=customer_id,
        old_name=old_name,
        new_name=new_name,
        request_type=request_type,
        document_path=document_path,
        document_type=document_type,
        status=RequestStatusEnum.SUBMITTED,
    )

    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # Log audit event
    audit_service.log_request_created(
        request_id=request_id,
        customer_id=customer_id,
        old_name=old_name,
        new_name=new_name,
        document_uploaded=document is not None,
    )

    # Start background processing
    from backend.config import DATABASE_URL
    background_tasks.add_task(
        process_request_async,
        request_id=request_id,
        customer_id=customer_id,
        old_name=old_name,
        new_name=new_name,
        document_path=document_path,
        db_url=DATABASE_URL,
    )

    return RequestResponse(
        request_id=db_request.request_id,
        customer_id=db_request.customer_id,
        old_name=db_request.old_name,
        new_name=db_request.new_name,
        request_type=db_request.request_type,
        document_path=db_request.document_path,
        status=RequestStatus(db_request.status.value),
        created_at=db_request.created_at,
        updated_at=db_request.updated_at,
    )


@router.post("/submit-json", response_model=RequestResponse)
async def submit_request_json(
    request: RequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submit a new name change request (JSON body, no document).

    Useful for testing without file upload.
    """
    request_id = generate_request_id()

    logger.info(f"Intake: New request {request_id} for customer {request.customer_id}")

    # Create database record
    db_request = PendingRequest(
        request_id=request_id,
        customer_id=request.customer_id,
        old_name=request.old_name,
        new_name=request.new_name,
        request_type=request.request_type,
        status=RequestStatusEnum.SUBMITTED,
    )

    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # Log audit event
    audit_service.log_request_created(
        request_id=request_id,
        customer_id=request.customer_id,
        old_name=request.old_name,
        new_name=request.new_name,
        document_uploaded=False,
    )

    # Start background processing
    from backend.config import DATABASE_URL
    background_tasks.add_task(
        process_request_async,
        request_id=request_id,
        customer_id=request.customer_id,
        old_name=request.old_name,
        new_name=request.new_name,
        document_path=None,
        db_url=DATABASE_URL,
    )

    return RequestResponse(
        request_id=db_request.request_id,
        customer_id=db_request.customer_id,
        old_name=db_request.old_name,
        new_name=db_request.new_name,
        request_type=db_request.request_type,
        status=RequestStatus(db_request.status.value),
        created_at=db_request.created_at,
        updated_at=db_request.updated_at,
    )
