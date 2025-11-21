#!/usr/bin/env python3
"""attestor_validation.py - Pure validation logic for attestation data.

This module provides static methods for validating attestation-related data
structures against the schemas and rules defined in attestor_config.py.
It is designed to be self-contained and free of side effects.
"""

from typing import Dict, List, Any
from datetime import datetime

from BachiCoin.lib_attestor.attestor_config import (
    AttestorConfig,
    is_valid_attestation_status,
)


class AttestorValidation:
    """Pure attestation validation logic, implemented as static methods."""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validates a single field against the attestor schema."""
        errors = []
        constraints = AttestorConfig._ATTESTOR_SCHEMA.get(field_name)

        if not constraints:
            return errors  # No rules defined for this field.

        # 1. Required check
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"'{field_name}' is required.")
            return errors  # Fail fast if a required field is missing.

        if value is None:
            return errors  # Not required and not present, so it's valid.

        # 2. Type check
        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                f"'{field_name}' must be of type {expected_type.__name__}, but got {type(value).__name__}."
            )
            return errors  # Stop further checks if type is wrong.

        # 3. Format and value checks
        if isinstance(value, str):
            if constraints.get("format") == "iso8601":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    errors.append(f"'{field_name}' has an invalid ISO 8601 format.")
        elif isinstance(value, (int, float)):
            if "min_value" in constraints and value < constraints["min_value"]:
                errors.append(
                    f"'{field_name}' value {value} is below the minimum of {constraints['min_value']}."
                )

        allowed = constraints.get("allowed_values")
        if allowed and value not in allowed:
            errors.append(
                f"'{field_name}' has an invalid value '{value}'. Must be one of: {allowed}."
            )

        return errors

    @staticmethod
    def validate_attestation_data(attestation_data: Dict[str, Any]) -> List[str]:
        """Performs a full validation of an attestation data dictionary."""
        errors = []

        # 1. Validate each field present in the data against the schema.
        for field, value in attestation_data.items():
            if field in AttestorConfig._ATTESTOR_SCHEMA:
                errors.extend(AttestorValidation.validate_field_by_schema(field, value))

        # 2. Cross-field business logic validation.
        if "attestation_id" in attestation_data and "slot" in attestation_data and "validator_index" in attestation_data:
            expected_id = f"{attestation_data['slot']}-{attestation_data['validator_index']}"
            if attestation_data["attestation_id"] != expected_id:
                errors.append(
                    f"Inconsistent 'attestation_id': expected '{expected_id}' (from slot-validator_index), got '{attestation_data['attestation_id']}'."
                )

        return errors

    @staticmethod
    def validate_for_creation(attestation_data: Dict[str, Any]) -> List[str]:
        """Validates data specifically for creating a new attestation record."""
        errors = []
        required_fields = [k for k, v in AttestorConfig._ATTESTOR_SCHEMA.items() if v.get("required")]
        for field in required_fields:
            if field not in attestation_data or attestation_data.get(field) is None:
                errors.append(f"Missing required field for creation: '{field}'.")

        if not errors:
            errors.extend(AttestorValidation.validate_attestation_data(attestation_data))
        return errors

    @staticmethod
    def validate_for_update(update_data: Dict[str, Any]) -> List[str]:
        """Validates data for an update, checking for immutable fields."""
        errors = []
        immutable_fields = [k for k, v in AttestorConfig._ATTESTOR_SCHEMA.items() if v.get("immutable")]

        for field in immutable_fields:
            if field in update_data:
                errors.append(f"Cannot update immutable field: '{field}'.")

        # Validate the types and values of the fields being updated.
        for field, value in update_data.items():
            if field in AttestorConfig._ATTESTOR_SCHEMA:
                errors.extend(AttestorValidation.validate_field_by_schema(field, value))

        return errors


# === Fail-fast Assertion Helpers ===

def assert_valid_for_creation(attestation_data: Dict[str, Any]) -> None:
    """Asserts that attestation data is valid for creation."""
    errors = AttestorValidation.validate_for_creation(attestation_data)
    assert not errors, f"Attestation creation validation failed: {errors}"


def assert_valid_for_update(update_data: Dict[str, Any]) -> None:
    """Asserts that update data is valid."""
    errors = AttestorValidation.validate_for_update(update_data)
    assert not errors, f"Attestation update validation failed: {errors}"


# === Self-Contained Unit Test ===

if __name__ == "__main__":
    """Unit test for the attestor_validation module."""
    print("=== Attestor Validation Test ===")

    valid_attestation = {
        "attestation_id": "320-123", "slot": 320, "epoch": 10, "validator_index": 123,
        "committee_index": 5, "status": "awaiting_duty",
    }
    print("\n🧪 1. Testing a valid attestation record for creation...")
    assert_valid_for_creation(valid_attestation)
    print("✅ PASSED: Valid attestation data is accepted.")

    print("\n🧪 2. Testing invalid data scenarios...")
    invalid_tests = {
        "Missing 'committee_index'": ("committee_index", None),
        "Incorrect type for 'epoch'": ("epoch", "ten"),
        "Negative 'inclusion_delay'": ("inclusion_delay", -1),
        "Invalid 'status'": ("status", "on_break"),
        "Inconsistent 'attestation_id'": ("attestation_id", "999-123"),
    }
    for name, (field, value) in invalid_tests.items():
        test_data = valid_attestation.copy()
        if value is None: del test_data[field]
        else: test_data[field] = value
        errors = AttestorValidation.validate_for_creation(test_data)
        print(f"   - {name}: {'PASSED' if errors else 'FAILED'}")
        assert errors, f"Test '{name}' should have failed but passed."

    print("\n🧪 3. Testing update validation...")
    valid_update = {"status": "included_success", "data_root": "0x" + "d" * 64}
    assert_valid_for_update(valid_update)
    print("   - Valid update data: PASSED")

    invalid_update = {"status": "missed", "validator_index": 999}
    errors_update = AttestorValidation.validate_for_update(invalid_update)
    print(f"   - Immutable field update: {'PASSED' if errors_update else 'FAILED'}")
    assert "Cannot update immutable field: 'validator_index'" in errors_update[0]

    print("\n✅ Attestor Validation Test Complete!")