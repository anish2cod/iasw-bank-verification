"""Audit logging service for IASW."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from backend.config import AUDIT_LOG_FILE

logger = logging.getLogger(__name__)


class AuditService:
    """
    Audit logging service that writes to JSONL file.
    Provides immutable audit trail for compliance.
    """

    def __init__(self, log_file: Path = AUDIT_LOG_FILE):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Action categories
        self.ACTION_CATEGORIES = {
            "REQUEST": ["CREATED", "UPDATED", "COMPLETED", "CANCELLED"],
            "DOCUMENT": ["UPLOADED", "PROCESSED", "VERIFIED", "REJECTED"],
            "AI": ["VALIDATION_STARTED", "VALIDATION_COMPLETED", "SCORING_COMPLETED"],
            "CHECKER": ["VIEWED", "APPROVED", "REJECTED", "ESCALATED"],
            "RPS": ["TOKEN_GENERATED", "UPDATE_ATTEMPTED", "UPDATE_COMPLETED"],
            "SYSTEM": ["ERROR", "WARNING", "INFO"],
        }

    def log(
        self,
        action: str,
        request_id: Optional[str] = None,
        actor: str = "SYSTEM",
        details: Optional[Dict[str, Any]] = None,
        category: str = "SYSTEM"
    ) -> Dict[str, Any]:
        """
        Log an audit event.

        Args:
            action: The action being logged (e.g., "REQUEST_CREATED")
            request_id: Associated request ID if applicable
            actor: Who performed the action (system, AI agent, checker ID)
            details: Additional details as dict
            category: Action category for filtering
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "category": category,
            "action": action,
            "request_id": request_id,
            "actor": actor,
            "details": details or {},
        }

        # Write to JSONL file
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
            logger.debug(f"Audit: {action} by {actor} for {request_id}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            raise

        return entry

    def log_request_created(
        self,
        request_id: str,
        customer_id: str,
        old_name: str,
        new_name: str,
        document_uploaded: bool = False
    ) -> Dict[str, Any]:
        """Log new request creation."""
        return self.log(
            action="REQUEST_CREATED",
            request_id=request_id,
            actor="INTAKE_SYSTEM",
            category="REQUEST",
            details={
                "customer_id": customer_id,
                "old_name": old_name,
                "new_name": new_name,
                "document_uploaded": document_uploaded,
            }
        )

    def log_document_processed(
        self,
        request_id: str,
        document_id: str,
        extracted_fields: Dict[str, Any],
        processing_time_ms: int
    ) -> Dict[str, Any]:
        """Log document processing completion."""
        return self.log(
            action="DOCUMENT_PROCESSED",
            request_id=request_id,
            actor="DOCUMENT_PROCESSOR_AGENT",
            category="DOCUMENT",
            details={
                "document_id": document_id,
                "extracted_fields": extracted_fields,
                "processing_time_ms": processing_time_ms,
            }
        )

    def log_ai_verification(
        self,
        request_id: str,
        recommendation: str,
        confidence_scores: Dict[str, Any],
        summary: str
    ) -> Dict[str, Any]:
        """Log AI verification result."""
        return self.log(
            action="AI_VERIFICATION_COMPLETED",
            request_id=request_id,
            actor="AI_ORCHESTRATOR",
            category="AI",
            details={
                "recommendation": recommendation,
                "confidence_scores": confidence_scores,
                "summary": summary[:500],  # Truncate long summaries
            }
        )

    def log_checker_action(
        self,
        request_id: str,
        checker_id: str,
        action: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log checker approval/rejection."""
        return self.log(
            action=f"CHECKER_{action}",
            request_id=request_id,
            actor=checker_id,
            category="CHECKER",
            details={
                "decision": action,
                "notes": notes,
            }
        )

    def log_rps_update(
        self,
        request_id: str,
        customer_id: str,
        old_name: str,
        new_name: str,
        success: bool,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log RPS update attempt."""
        return self.log(
            action="RPS_UPDATE_COMPLETED" if success else "RPS_UPDATE_FAILED",
            request_id=request_id,
            actor="RPS_GATEWAY",
            category="RPS",
            details={
                "customer_id": customer_id,
                "old_name": old_name,
                "new_name": new_name,
                "success": success,
                "error": error,
            }
        )

    def get_request_history(self, request_id: str) -> List[Dict[str, Any]]:
        """Get all audit entries for a specific request."""
        entries = []
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        if entry.get("request_id") == request_id:
                            entries.append(entry)
        except FileNotFoundError:
            pass
        return entries

    def get_recent_entries(
        self,
        limit: int = 100,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent audit entries, optionally filtered by category."""
        entries = []
        try:
            with open(self.log_file, "r") as f:
                all_lines = f.readlines()
                # Read from end for efficiency
                for line in reversed(all_lines):
                    if line.strip():
                        entry = json.loads(line)
                        if category is None or entry.get("category") == category:
                            entries.append(entry)
                        if len(entries) >= limit:
                            break
        except FileNotFoundError:
            pass
        return entries


# Singleton instance
audit_service = AuditService()
