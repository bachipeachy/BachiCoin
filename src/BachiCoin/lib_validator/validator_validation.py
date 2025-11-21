#!/usr/bin/env python3
"""validator_validation.py - Pure validation for validator data with fail-fast assertions"""

from datetime import datetime
from typing import Dict, List, Any

from BachiCoin.lib_validator.validator_config import (
    ValidatorConfig,
    get_validator_schema_view,
    is_valid_pubkey,
    is_valid_withdrawal_credentials,
    is_valid_validator_status,
)


class ValidatorValidation:
    """Pure validator validation - static methods only"""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validate a single field using schema constraints from ValidatorConfig."""
        errors = []
        # This assumes a helper in ValidatorConfig to get constraints for a field
        # For now, we'll get the full schema and check the field.
        schema = get_validator_schema_view("validator_full")
        constraints = schema.get(field_name)

        if not constraints:
            return [f"Field '{field_name}' not found in validator schema"]

        # Required check
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"{field_name} is required")
            return errors

        if value is None:
            return errors

        # Type check
        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"{field_name} must be {expected_type.__name__}, not {type(value).__name__}")

        # Numeric validations
        if isinstance(value, (int, float)):
            if "min_value" in constraints and value < constraints["min_value"]:
                errors.append(f"{field_name} ({value}) is below minimum of {constraints['min_value']}")
            if "max_value" in constraints and value > constraints["max_value"]:
                errors.append(f"{field_name} ({value}) is above maximum of {constraints['max_value']}")

        return errors

    @staticmethod
    def validate_required_fields(validator_data: Dict[str, Any], view: str) -> List[str]:
        """Validate that all required fields for a given view are present."""
        errors = []
        schema = get_validator_schema_view(view)
        required_fields = [field for field, constraints in schema.items() if constraints.get("required")]

        for field in required_fields:
            if field not in validator_data or validator_data[field] is None:
                errors.append(f"Missing required field for '{view}' view: {field}")

        return errors

    @staticmethod
    def validate_field_formats(validator_data: Dict[str, Any]) -> List[str]:
        """Validate field formats using functions from validator_config."""
        errors = []
        if "pubkey" in validator_data and not is_valid_pubkey(validator_data["pubkey"]):
            errors.append("Invalid pubkey format")
        if "withdrawal_credentials" in validator_data and not is_valid_withdrawal_credentials(validator_data["withdrawal_credentials"]):
            errors.append("Invalid withdrawal_credentials format")
        if "status" in validator_data and not is_valid_validator_status(validator_data["status"]):
            errors.append(f"Invalid status: {validator_data['status']}")
        return errors

    @staticmethod
    def is_valid_timestamp(timestamp: str) -> bool:
        """Validate ISO timestamp format."""
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_timestamps(validator_data: Dict[str, Any]) -> List[str]:
        """Validate timestamp fields."""
        errors = []
        for field in ["created_at", "updated_at"]:
            if field in validator_data and validator_data[field]:
                if not ValidatorValidation.is_valid_timestamp(validator_data[field]):
                    errors.append(f"Invalid timestamp format for {field}")
        return errors

    @staticmethod
    def validate_validator_data(validator_data: Dict[str, Any], view: str = "validator_full") -> List[str]:
        """Main validation function - returns list of errors (empty if valid)."""
        errors = []
        errors.extend(ValidatorValidation.validate_required_fields(validator_data, view))
        errors.extend(ValidatorValidation.validate_field_formats(validator_data))
        errors.extend(ValidatorValidation.validate_timestamps(validator_data))

        # Validate all fields present against their schema constraints
        for field, value in validator_data.items():
            errors.extend(ValidatorValidation.validate_field_by_schema(field, value))

        return list(sorted(set(errors))) # Return unique errors

    @staticmethod
    def validate_for_update(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> List[str]:
        """Validate for a validator update operation."""
        errors = []
        schema = get_validator_schema_view("validator_full")
        immutable_fields = [field for field, constraints in schema.items() if constraints.get("immutable")]

        for field in immutable_fields:
            if field in update_data and update_data[field] != current_data.get(field):
                errors.append(f"Cannot update immutable field: {field}")

        merged_data = current_data.copy()
        merged_data.update(update_data)
        errors.extend(ValidatorValidation.validate_validator_data(merged_data))

        return list(sorted(set(errors)))


# Public-facing helper functions
def get_validation_errors(validator_data: Dict[str, Any], view: str = "validator_full") -> List[str]:
    """Get a list of validation errors for the given validator data."""
    return ValidatorValidation.validate_validator_data(validator_data, view)

def assert_valid_validator_data(validator_data: Dict[str, Any], view: str = "validator_full") -> None:
    """Assert that validator data is valid, failing fast if not."""
    errors = ValidatorValidation.validate_validator_data(validator_data, view)
    assert not errors, f"Validator data validation failed: {errors}"

def assert_valid_update_data(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> None:
    """Assert that an update to validator data is valid."""
    errors = ValidatorValidation.validate_for_update(current_data, update_data)
    assert not errors, f"Validator update validation failed: {errors}"


if __name__ == "__main__":
    """Unit test for the ValidatorValidation class."""
    print("=== ValidatorValidation Unit Test ===")

    # Create a valid test validator record
    test_validator = {
        "validator_index": 1,
        "pubkey": "0x" + "a" * 96,
        "withdrawal_credentials": "0x" + "b" * 64,
        "effective_balance": 32000000000,
        "slashed": False,
        "activation_eligibility_epoch": 2**64 - 1,
        "activation_epoch": 2**64 - 1,
        "exit_epoch": 2**64 - 1,
        "withdrawable_epoch": 2**64 - 1,
        "status": "pending_initialized",
        "balance": 0,
        "last_attestation_slot": None,
        "created_at": datetime.now().isoformat() + "Z",
        "updated_at": datetime.now().isoformat() + "Z",
    }

    print("\n🧪 Testing with valid data...")
    errors = get_validation_errors(test_validator)
    print(f"✅ Validation result: {'OK' if not errors else 'Failed'}")
    assert not errors, f"Validation failed unexpectedly: {errors}"

    print("\n🧪 Testing with invalid data...")
    invalid_validator = test_validator.copy()
    invalid_validator["pubkey"] = "0x123"  # Invalid format
    invalid_validator["status"] = "invalid_status"
    invalid_validator["effective_balance"] = -100  # Below minimum
    errors = get_validation_errors(invalid_validator)
    print(f"✅ Validation correctly found {len(errors)} errors.")
    for error in errors:
        print(f"  - Found expected error: {error}")
    assert len(errors) > 0

    print("\n🧪 Testing update validation...")
    valid_update = {"status": "active_ongoing"}
    invalid_update = {"pubkey": "0x" + "c" * 96} # Trying to change immutable field

    update_errors_valid = ValidatorValidation.validate_for_update(test_validator, valid_update)
    print(f"✅ Valid update check: {'OK' if not update_errors_valid else 'Failed'}")
    assert not update_errors_valid

    update_errors_invalid = ValidatorValidation.validate_for_update(test_validator, invalid_update)
    print(f"✅ Invalid update check (should fail): {'OK' if update_errors_invalid else 'Failed'}")
    assert "Cannot update immutable field: pubkey" in update_errors_invalid

    print("\n✅ ValidatorValidation Test Complete!")