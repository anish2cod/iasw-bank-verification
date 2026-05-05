"""Validation Agent - Validates customer exists and request is valid."""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from backend.services.rps_mock import rps_service

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validation check."""
    is_valid: bool
    customer_exists: bool
    name_matches: bool
    account_active: bool
    errors: list
    warnings: list
    customer_data: Optional[Dict[str, Any]] = None


class ValidationAgent:
    """
    Agent responsible for validating request data against RPS.

    Checks:
    - Customer exists in RPS
    - Current name matches old_name in request
    - Account is active (not closed/dormant)
    - No duplicate pending requests
    """

    def __init__(self):
        self.rps = rps_service

    async def validate(
        self,
        customer_id: str,
        old_name: str,
        new_name: str,
        pending_requests: Optional[list] = None
    ) -> ValidationResult:
        """
        Validate a name change request.

        Args:
            customer_id: Customer ID to validate
            old_name: Current name (should match RPS)
            new_name: Requested new name
            pending_requests: List of pending request IDs for this customer

        Returns:
            ValidationResult with status and details
        """
        errors = []
        warnings = []

        logger.info(f"ValidationAgent: Starting validation for {customer_id}")

        # Check customer exists
        customer = self.rps.get_customer(customer_id)
        customer_exists = customer is not None

        if not customer_exists:
            errors.append(f"Customer {customer_id} not found in RPS")
            return ValidationResult(
                is_valid=False,
                customer_exists=False,
                name_matches=False,
                account_active=False,
                errors=errors,
                warnings=warnings,
            )

        # Check name matches
        name_matches = self.rps.validate_customer_name(customer_id, old_name)
        if not name_matches:
            errors.append(
                f"Name mismatch: RPS has '{customer['name']}', "
                f"request has '{old_name}'"
            )

        # Check account status
        account_status = customer.get("account_status", "UNKNOWN")
        account_active = account_status == "ACTIVE"

        if not account_active:
            if account_status == "DORMANT":
                warnings.append(
                    f"Account is DORMANT - may require reactivation first"
                )
            else:
                errors.append(f"Account status is {account_status} - cannot process")

        # Check for duplicate requests
        if pending_requests and len(pending_requests) > 0:
            warnings.append(
                f"Customer has {len(pending_requests)} other pending request(s)"
            )

        # Validate new name is different
        if old_name.lower().strip() == new_name.lower().strip():
            errors.append("New name is the same as current name")

        # Validate name format (basic checks)
        if len(new_name.strip()) < 2:
            errors.append("New name is too short")

        if any(char.isdigit() for char in new_name):
            warnings.append("New name contains numbers - verify if intentional")

        is_valid = len(errors) == 0 and customer_exists and name_matches

        logger.info(
            f"ValidationAgent: Validation complete for {customer_id}. "
            f"Valid: {is_valid}, Errors: {len(errors)}, Warnings: {len(warnings)}"
        )

        return ValidationResult(
            is_valid=is_valid,
            customer_exists=customer_exists,
            name_matches=name_matches,
            account_active=account_active,
            errors=errors,
            warnings=warnings,
            customer_data=customer,
        )

    def get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer information from RPS."""
        return self.rps.get_customer(customer_id)
