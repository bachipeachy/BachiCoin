#!/usr/bin/env python3
"""finalizer_validation.py - Pure validation logic for finality data.

This module provides static methods for validating checkpoint-related data
structures against the schemas and rules defined in finalizer_config.py.
It is designed to be self-contained and free of side effects.
"""

from typing import Dict, List, Any
from datetime import datetime

from BachiCoin.lib_finalizer.finalizer_config import (
    FinalizerConfig,
    is_valid_finality_status,
)


class FinalizerValidation:
    """Pure finality validation logic, implemented as static methods."""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validates a single field against the checkpoint schema."""
        errors = []
        constraints = FinalizerConfig._CHECKPOINT_SCHEMA.get(field_name)

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
    def validate_checkpoint_data(checkpoint_data: Dict[str, Any]) -> List[str]:
        """Performs a full validation of a checkpoint data dictionary."""
        errors = []
        for field, value in checkpoint_data.items():
            if field in FinalizerConfig._CHECKPOINT_SCHEMA:
                errors.extend(FinalizerValidation.validate_field_by_schema(field, value))
        return errors

    @staticmethod
    def validate_for_creation(checkpoint_data: Dict[str, Any]) -> List[str]:
        """Validates data specifically for creating a new checkpoint record."""
        errors = []
        required_fields = [k for k, v in FinalizerConfig._CHECKPOINT_SCHEMA.items() if v.get("required")]
        for field in required_fields:
            if field not in checkpoint_data or checkpoint_data.get(field) is None:
                errors.append(f"Missing required field for creation: '{field}'.")

        if not errors:
            errors.extend(FinalizerValidation.validate_checkpoint_data(checkpoint_data))
        return errors

    @staticmethod
    def validate_for_update(update_data: Dict[str, Any]) -> List[str]:
        """Validates data for an update, checking for immutable fields."""
        errors = []
        immutable_fields = [k for k, v in FinalizerConfig._CHECKPOINT_SCHEMA.items() if v.get("immutable")]

        for field in immutable_fields:
            if field in update_data:
                errors.append(f"Cannot update immutable field: '{field}'.")

        # Validate the types and values of the fields being updated.
        for field, value in update_data.items():
            if field in FinalizerConfig._CHECKPOINT_SCHEMA:
                errors.extend(FinalizerValidation.validate_field_by_schema(field, value))

        return errors


# === Fail-fast Assertion Helpers ===

def assert_valid_for_creation(checkpoint_data: Dict[str, Any]) -> None:
    """Asserts that checkpoint data is valid for creation."""
    errors = FinalizerValidation.validate_for_creation(checkpoint_data)
    assert not errors, f"Checkpoint creation validation failed: {errors}"


def assert_valid_for_update(update_data: Dict[str, Any]) -> None:
    """Asserts that update data is valid."""
    errors = FinalizerValidation.validate_for_update(update_data)
    assert not errors, f"Checkpoint update validation failed: {errors}"


# === Self-Contained Unit Test ===

if __name__ == "__main__":
    """Unit test for the finalizer_validation module."""
    print("=== Finalizer Validation Test ===")

    valid_checkpoint = {
        "epoch": 100, "root": "0x" + "f" * 64, "status": "justified",
    }
    print("\n🧪 1. Testing a valid checkpoint record for creation...")
    assert_valid_for_creation(valid_checkpoint)
    print("✅ PASSED: Valid checkpoint data is accepted.")

    print("\n🧪 2. Testing invalid data scenarios...")
    invalid_tests = {
        "Missing 'root'": ("root", None),
        "Incorrect type for 'epoch'": ("epoch", "one-hundred"),
        "Negative 'participating_stake'": ("participating_stake", -1000),
        "Invalid 'status'": ("status", "pending"),
    }
    for name, (field, value) in invalid_tests.items():
        test_data = valid_checkpoint.copy()
        if value is None: del test_data[field]
        else: test_data[field] = value
        errors = FinalizerValidation.validate_for_creation(test_data)
        print(f"   - {name}: {'PASSED' if errors else 'FAILED'}")
        assert errors, f"Test '{name}' should have failed but passed."

    print("\n🧪 3. Testing update validation...")
    valid_update = {"status": "finalized", "finalized_at": datetime.now().isoformat() + "Z"}
    assert_valid_for_update(valid_update)
    print("   - Valid update data: PASSED")

    invalid_update = {"status": "finalized", "epoch": 101}
    errors_update = FinalizerValidation.validate_for_update(invalid_update)
    print(f"   - Immutable field update: {'PASSED' if errors_update else 'FAILED'}")
    assert "Cannot update immutable field: 'epoch'" in errors_update[0]

    print("\n✅ Finalizer Validation Test Complete!")