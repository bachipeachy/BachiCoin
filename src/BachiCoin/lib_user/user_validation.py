#!/usr/bin/env python3
"""
user_validation.py

A pure, stateless validation engine for user data. This module contains
static methods for validating user data against the schema and business rules
defined in user_config.py. It has no external dependencies.
"""

from datetime import datetime
from typing import Dict, List, Any, Callable

from BachiCoin.lib_user.user_config import (
    UserConfig,
    UserType,
    is_valid_user_id,
    is_valid_email,
    is_valid_phone,
    is_valid_user_type,
    is_valid_user_status,
    is_valid_language,
    is_valid_currency,
    get_max_wallets,
    get_min_stake
)


class UserValidation:
    """A collection of pure, static methods for user data validation."""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any, user_data: Dict[str, Any]) -> List[str]:
        """
        Validates a single field's value against the master schema.

        Args:
            field_name: The name of the field to validate.
            value: The value of the field.
            user_data: The full user data object, providing context for validation.

        Returns:
            A list of error strings. An empty list means the field is valid.
        """
        errors = []
        constraints = UserConfig.get_field_constraints(field_name)

        if not constraints:
            return []  # No constraints for this field

        # Required check
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"'{field_name}' is required")
            return errors  # Stop further validation if required field is missing

        if value is None:
            return []  # Not required and no value, so it's valid

        # Type check
        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"'{field_name}' must be of type {expected_type.__name__}, but got {type(value).__name__}")
            return errors  # Stop further validation if type is wrong

        # String validations
        if isinstance(value, str):
            if "min_length" in constraints and len(value.strip()) < constraints["min_length"]:
                errors.append(f"'{field_name}' is too short")
            if "max_length" in constraints and len(value) > constraints["max_length"]:
                errors.append(f"'{field_name}' is too long")

        # Numeric validations
        if isinstance(value, (int, float)):
            if "min_value" in constraints and value < constraints["min_value"]:
                errors.append(f"'{field_name}' is below the minimum value")
            if "max_value" in constraints and value > constraints["max_value"]:
                errors.append(f"'{field_name}' is above the maximum value")

        # List validations (Context-aware)
        if field_name == "wallet_ids" and isinstance(value, list):
            user_type = user_data.get("user_type", UserConfig.DEFAULT_USER_TYPE)
            max_wallets = get_max_wallets(user_type)
            if len(value) > max_wallets:
                errors.append(f"Exceeds wallet limit for user type '{user_type}': {len(value)} > {max_wallets}")

        # Allowed values check
        allowed = constraints.get("allowed_values")
        if allowed and value not in allowed:
            errors.append(f"'{value}' is not an allowed value for '{field_name}'")

        return errors

    @staticmethod
    def validate_required_fields(user_data: Dict[str, Any], view: str) -> List[str]:
        """Validates that all required fields for a given view are present."""
        errors = []
        required_fields = UserConfig.get_required_fields(view)

        for field in required_fields:
            if user_data.get(field) is None or user_data.get(field) == "":
                errors.append(f"Missing required field for '{view}' view: '{field}'")
        return errors

    @staticmethod
    def validate_field_formats(user_data: Dict[str, Any]) -> List[str]:
        """Validates specific field formats like email, phone, etc."""
        errors = []
        # Using .get() to avoid KeyErrors for optional fields
        if user_data.get("user_id") and not is_valid_user_id(user_data["user_id"]):
            errors.append("Invalid 'user_id' format")
        if user_data.get("email_registration") and not is_valid_email(user_data["email_registration"]):
            errors.append("Invalid 'email_registration' format")
        if user_data.get("email_current") and not is_valid_email(user_data["email_current"]):
            errors.append("Invalid 'email_current' format")
        if user_data.get("phone") and not is_valid_phone(user_data["phone"]):
            errors.append("Invalid 'phone' format")
        return errors

    @staticmethod
    def validate_timestamps(user_data: Dict[str, Any]) -> List[str]:
        """Validates that timestamp fields are in the correct ISO 8601 format."""
        errors = []
        for field in ["created_at", "last_modified"]:
            if user_data.get(field) and not UserValidation.is_valid_iso_timestamp(user_data[field]):
                errors.append(f"Invalid ISO 8601 format for '{field}'")
        return errors

    @staticmethod
    def validate_business_rules(user_data: Dict[str, Any], view: str = "full_schema") -> List[str]:
        """Validates high-level business logic rules based on the validation context (view)."""
        errors = []
        user_type = user_data.get("user_type")

        # Validator-specific rules
        if user_type == UserType.VALIDATOR.value:
            # On creation or indexing, a validator does not need a stake. This is added/validated later.
            if view not in ["create", "index"]:
                min_stake = get_min_stake(user_type)
                current_stake = user_data.get("stake_amount") or 0
                if current_stake < min_stake:
                    errors.append(f"Validator stake of {current_stake} is below minimum of {min_stake}")
            
            if not user_data.get("kyc_verified"):
                errors.append("Validators must be KYC verified")

        # Non-validators should not have validator-specific data
        if user_type != UserType.VALIDATOR.value:
            if user_data.get("stake_amount"):
                errors.append("Non-validators cannot have a 'stake_amount'")
            if user_data.get("validator_address"):
                errors.append("Non-validators cannot have a 'validator_address'")

        # Business type validation
        if user_type == UserType.BUSINESS.value and not user_data.get("organization_name"):
            errors.append("Users of type 'business' must have an 'organization_name'")

        return errors

    @staticmethod
    def is_valid_iso_timestamp(timestamp: str) -> bool:
        """Validates if a string is a compliant ISO 8601 timestamp."""
        try:
            # Handles both 'Z' and '+00:00' UTC designators
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_user_data(user_data: Dict[str, Any], view: str = "full_schema") -> List[str]:
        """
        Main validation entry point. Runs a comprehensive set of checks.

        Args:
            user_data: The user data dictionary to validate.
            view: The schema view to validate against (e.g., 'create', 'update').

        Returns:
            A list of all validation errors. An empty list indicates the data is valid.
        """
        errors = UserValidation.validate_required_fields(user_data, view)
        errors.extend(UserValidation.validate_field_formats(user_data))
        errors.extend(UserValidation.validate_timestamps(user_data))
        errors.extend(UserValidation.validate_business_rules(user_data, view))

        # Iterate and validate all fields present in the data against the schema
        for field, value in user_data.items():
            errors.extend(UserValidation.validate_field_by_schema(field, value, user_data))

        return sorted(list(set(errors)))  # Return unique, sorted errors

    @staticmethod
    def validate_for_update(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> List[str]:
        """Validates a proposed update against the current user data."""
        errors = []
        immutable_fields = UserConfig.get_immutable_fields()
        for field in immutable_fields:
            if field in update_data and update_data[field] != current_data.get(field):
                errors.append(f"Cannot update immutable field: '{field}'")

        if errors:
            return errors  # Fail early if immutable fields are being changed

        # Create a merged view of the data and validate it
        merged_data = {**current_data, **update_data}
        errors.extend(UserValidation.validate_user_data(merged_data, "full_schema"))

        return sorted(list(set(errors)))


# --- Fail-Fast Assertion Helpers for Development ---

def assert_valid_user_data(user_data: Dict[str, Any], view: str = "full_schema") -> None:
    """Asserts that user data is valid for a given view, failing fast if not."""
    errors = UserValidation.validate_user_data(user_data, view)
    assert not errors, f"User data validation failed: {errors}"


def assert_valid_update_data(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> None:
    """Asserts that an update is valid, failing fast if not."""
    errors = UserValidation.validate_for_update(current_data, update_data)
    assert not errors, f"User update validation failed: {errors}"


if __name__ == "__main__":
    """A simple smoke test to verify that the validation module can be loaded."""
    print("--- Running UserValidation Smoke Test ---")
    try:
        # 1. Test a valid field
        valid_email = "test@example.com"
        errors = UserValidation.validate_field_by_schema("email_current", valid_email, {})
        assert not errors, f"Validation of a valid email failed: {errors}"
        print("✅ Validation of a single valid field works.")

        # 2. Test an invalid field
        invalid_email = "not-an-email"
        errors = UserValidation.validate_field_formats({"email_current": invalid_email})
        assert errors, "Validation of an invalid email should have failed."
        print("✅ Detection of an invalid field format works.")

        # 3. Test a business rule
        invalid_validator = {"user_type": "validator", "kyc_verified": False}
        errors = UserValidation.validate_business_rules(invalid_validator, "update") # Test with 'update' view
        assert errors, "Validation of a business rule should have failed."
        print("✅ Validation of a business rule works.")

        # 4. Test the main entry point with a valid payload
        valid_user = {
            "user_id": "U_a94d9554fa3dfe35", # Updated to new format
            "first_name": "Test",
            "last_name": "User",
            "email_registration": "test@example.com",
            "email_current": "test@example.com",
            "kyc_key": "Test|User|test@example.com",
            "user_type": "testnet",
            "status": "active",
            "created_at": "2023-01-01T00:00:00Z",
            "last_modified": "2023-01-01T00:00:00Z"
        }
        errors = UserValidation.validate_user_data(valid_user, "create")
        assert not errors, f"Validation of a valid user object failed: {errors}"
        print("✅ Full validation of a valid user object works.")

        print("\n--- UserValidation Smoke Test Passed Successfully! ---")
    except Exception as e:
        print("\n--- ❌ UserValidation Smoke Test FAILED! ❌ ---")
        print(f"Error: {e}")
        raise
