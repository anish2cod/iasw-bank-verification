"""Mock RPS (Retail Processing System) - Core Banking Simulator."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import secrets

logger = logging.getLogger(__name__)


class RPSMockService:
    """
    Mock core banking system that simulates RPS functionality.
    In production, this would connect to the actual RPS via API/messaging.
    """

    def __init__(self):
        # Mock customer database
        self._customers: Dict[str, Dict[str, Any]] = {
            "C001": {
                "customer_id": "C001",
                "name": "Priya Sharma",
                "date_of_birth": "1990-05-15",
                "address": "123 MG Road, Mumbai 400001",
                "account_status": "ACTIVE",
                "accounts": ["ACC001", "ACC002"],
                "created_at": "2018-03-20",
            },
            "C002": {
                "customer_id": "C002",
                "name": "Rahul Kumar",
                "date_of_birth": "1985-08-22",
                "address": "456 Park Street, Kolkata 700016",
                "account_status": "ACTIVE",
                "accounts": ["ACC003"],
                "created_at": "2019-07-11",
            },
            "C003": {
                "customer_id": "C003",
                "name": "Anita Desai",
                "date_of_birth": "1992-11-30",
                "address": "789 Brigade Road, Bangalore 560001",
                "account_status": "ACTIVE",
                "accounts": ["ACC004", "ACC005"],
                "created_at": "2020-01-05",
            },
            "C004": {
                "customer_id": "C004",
                "name": "Vikram Singh",
                "date_of_birth": "1988-02-14",
                "address": "321 Civil Lines, Delhi 110054",
                "account_status": "DORMANT",
                "accounts": ["ACC006"],
                "created_at": "2017-09-18",
            },
        }

        # Valid approval tokens (simulating token validation)
        self._valid_tokens: Dict[str, Dict[str, Any]] = {}

        # Change history
        self._change_history: list = []

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve customer details from RPS."""
        customer = self._customers.get(customer_id)
        if customer:
            logger.info(f"RPS: Retrieved customer {customer_id}")
            return customer.copy()
        logger.warning(f"RPS: Customer {customer_id} not found")
        return None

    def customer_exists(self, customer_id: str) -> bool:
        """Check if customer exists in RPS."""
        exists = customer_id in self._customers
        logger.info(f"RPS: Customer {customer_id} exists: {exists}")
        return exists

    def validate_customer_name(self, customer_id: str, name: str) -> bool:
        """Validate that the given name matches the customer's current name."""
        customer = self._customers.get(customer_id)
        if not customer:
            return False
        current_name = customer.get("name", "").lower().strip()
        check_name = name.lower().strip()
        matches = current_name == check_name
        logger.info(f"RPS: Name validation for {customer_id}: {matches}")
        return matches

    def register_approval_token(
        self,
        token: str,
        request_id: str,
        checker_id: str,
        customer_id: str,
        new_name: str
    ) -> bool:
        """Register an approval token for RPS update."""
        self._valid_tokens[token] = {
            "request_id": request_id,
            "checker_id": checker_id,
            "customer_id": customer_id,
            "new_name": new_name,
            "created_at": datetime.utcnow().isoformat(),
            "used": False,
        }
        logger.info(f"RPS: Registered approval token for request {request_id}")
        return True

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate an approval token."""
        token_data = self._valid_tokens.get(token)
        if not token_data:
            logger.warning(f"RPS: Invalid token attempted")
            return None
        if token_data.get("used"):
            logger.warning(f"RPS: Token already used")
            return None
        return token_data

    def update_customer_name(
        self,
        customer_id: str,
        new_name: str,
        approval_token: str
    ) -> Dict[str, Any]:
        """
        Update customer name in RPS.
        Requires valid approval token (HITL enforcement).
        """
        # Validate token
        token_data = self.validate_token(approval_token)
        if not token_data:
            return {
                "success": False,
                "error": "Invalid or expired approval token",
                "code": "INVALID_TOKEN"
            }

        # Verify token matches this customer and name
        if token_data["customer_id"] != customer_id:
            return {
                "success": False,
                "error": "Token not valid for this customer",
                "code": "TOKEN_CUSTOMER_MISMATCH"
            }

        if token_data["new_name"] != new_name:
            return {
                "success": False,
                "error": "Token not valid for this name change",
                "code": "TOKEN_NAME_MISMATCH"
            }

        # Check customer exists
        if customer_id not in self._customers:
            return {
                "success": False,
                "error": f"Customer {customer_id} not found",
                "code": "CUSTOMER_NOT_FOUND"
            }

        # Perform the update
        old_name = self._customers[customer_id]["name"]
        self._customers[customer_id]["name"] = new_name
        self._customers[customer_id]["last_updated"] = datetime.utcnow().isoformat()

        # Mark token as used
        self._valid_tokens[approval_token]["used"] = True
        self._valid_tokens[approval_token]["used_at"] = datetime.utcnow().isoformat()

        # Record in history
        self._change_history.append({
            "customer_id": customer_id,
            "old_name": old_name,
            "new_name": new_name,
            "approval_token": approval_token[:8] + "...",  # Partial for security
            "checker_id": token_data["checker_id"],
            "timestamp": datetime.utcnow().isoformat(),
        })

        logger.info(f"RPS: Updated customer {customer_id} name: {old_name} -> {new_name}")

        return {
            "success": True,
            "customer_id": customer_id,
            "old_name": old_name,
            "new_name": new_name,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def get_change_history(self, customer_id: Optional[str] = None) -> list:
        """Get name change history, optionally filtered by customer."""
        if customer_id:
            return [h for h in self._change_history if h["customer_id"] == customer_id]
        return self._change_history.copy()

    def generate_approval_token(self) -> str:
        """Generate a secure approval token."""
        return secrets.token_urlsafe(32)


# Singleton instance
rps_service = RPSMockService()
