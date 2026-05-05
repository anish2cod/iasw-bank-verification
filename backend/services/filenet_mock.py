"""Mock FileNet - Document Management System Simulator."""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib
import uuid

from backend.config import UPLOAD_DIR

logger = logging.getLogger(__name__)


class FileNetMockService:
    """
    Mock document management system simulating FileNet functionality.
    In production, this would connect to actual FileNet via P8 API.
    """

    def __init__(self, storage_path: Path = UPLOAD_DIR):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Document metadata store
        self._documents: Dict[str, Dict[str, Any]] = {}

        # Document class definitions
        self._document_classes = {
            "MARRIAGE_CERTIFICATE": {
                "required_fields": ["bride_name", "groom_name", "marriage_date"],
                "retention_days": 2555,  # 7 years
            },
            "COURT_ORDER": {
                "required_fields": ["petitioner_name", "order_date", "order_type"],
                "retention_days": 2555,
            },
            "GOVERNMENT_ID": {
                "required_fields": ["name", "id_number", "expiry_date"],
                "retention_days": 365,
            },
        }

    def store_document(
        self,
        file_content: bytes,
        filename: str,
        document_class: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a document in FileNet mock.
        Returns document ID and storage path.
        """
        # Generate document ID
        doc_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"

        # Calculate checksum
        checksum = hashlib.sha256(file_content).hexdigest()

        # Create storage path with date-based folder structure
        date_folder = datetime.utcnow().strftime("%Y/%m/%d")
        storage_dir = self.storage_path / date_folder
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename and add doc_id prefix
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")
        storage_filename = f"{doc_id}_{safe_filename}"
        storage_path = storage_dir / storage_filename

        # Write file
        with open(storage_path, "wb") as f:
            f.write(file_content)

        # Store metadata
        doc_metadata = {
            "document_id": doc_id,
            "filename": filename,
            "storage_path": str(storage_path),
            "document_class": document_class,
            "checksum": checksum,
            "size_bytes": len(file_content),
            "content_type": self._guess_content_type(filename),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": "SYSTEM",
            "custom_metadata": metadata or {},
            "version": 1,
            "status": "ACTIVE",
        }

        self._documents[doc_id] = doc_metadata
        logger.info(f"FileNet: Stored document {doc_id}: {filename}")

        return {
            "document_id": doc_id,
            "storage_path": str(storage_path),
            "checksum": checksum,
        }

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve document metadata by ID."""
        doc = self._documents.get(document_id)
        if doc:
            logger.info(f"FileNet: Retrieved metadata for {document_id}")
            return doc.copy()
        logger.warning(f"FileNet: Document {document_id} not found")
        return None

    def get_document_content(self, document_id: str) -> Optional[bytes]:
        """Retrieve document content by ID."""
        doc = self._documents.get(document_id)
        if not doc:
            logger.warning(f"FileNet: Document {document_id} not found")
            return None

        storage_path = Path(doc["storage_path"])
        if not storage_path.exists():
            logger.error(f"FileNet: File missing for {document_id}")
            return None

        with open(storage_path, "rb") as f:
            content = f.read()

        logger.info(f"FileNet: Retrieved content for {document_id}")
        return content

    def delete_document(self, document_id: str) -> bool:
        """Soft delete a document (mark as deleted, don't remove)."""
        doc = self._documents.get(document_id)
        if not doc:
            return False

        doc["status"] = "DELETED"
        doc["deleted_at"] = datetime.utcnow().isoformat()
        logger.info(f"FileNet: Soft deleted {document_id}")
        return True

    def search_documents(
        self,
        document_class: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        status: str = "ACTIVE"
    ) -> List[Dict[str, Any]]:
        """Search documents by class and/or metadata."""
        results = []
        for doc in self._documents.values():
            if doc["status"] != status:
                continue
            if document_class and doc["document_class"] != document_class:
                continue
            if metadata_filter:
                custom = doc.get("custom_metadata", {})
                if not all(custom.get(k) == v for k, v in metadata_filter.items()):
                    continue
            results.append(doc.copy())

        logger.info(f"FileNet: Search returned {len(results)} documents")
        return results

    def update_metadata(
        self,
        document_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Update document custom metadata."""
        doc = self._documents.get(document_id)
        if not doc:
            return False

        doc["custom_metadata"].update(metadata)
        doc["updated_at"] = datetime.utcnow().isoformat()
        logger.info(f"FileNet: Updated metadata for {document_id}")
        return True

    def link_to_request(
        self,
        document_id: str,
        request_id: str
    ) -> bool:
        """Link a document to a service request."""
        doc = self._documents.get(document_id)
        if not doc:
            return False

        if "linked_requests" not in doc:
            doc["linked_requests"] = []
        doc["linked_requests"].append(request_id)
        logger.info(f"FileNet: Linked {document_id} to request {request_id}")
        return True

    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename extension."""
        ext = Path(filename).suffix.lower()
        content_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
        }
        return content_types.get(ext, "application/octet-stream")


# Singleton instance
filenet_service = FileNetMockService()
