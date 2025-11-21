#!/usr/bin/env python3
"""
wallet_validation.py

This module provides a centralized, static validation service for the BachiCoin
wallet. It enforces all data integrity rules, formats, and business logic
defined in the wallet_config module. All validation logic should reside here.
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Callable

from BachiCoin.lib_wallet.wallet_config import (
    WalletConfig,
    WalletType,
    AccountType,
    WalletSecurityType,
    Network,
    Currency,
    WalletStatus
)
# Import the user ID validator directly from the user module
from BachiCoin.lib_user.user_config import is_valid_user_id
from BachiCoin.lib_transaction.tx_config import DECIMAL_PLACES # Import DECIMAL_PLACES


# --- Validation Helper Functions ---
# These are kept at the module level for clarity and reusability within this file.

def _is_valid_format(pattern: re.Pattern, value: str) -> bool:
    """Checks if a string value matches a given regex pattern."""
    return isinstance(value, str) and bool(pattern.match(value))


def _format_balance(balance: float) -> float:
    """Formats balance to the standard precision."""
    return round(balance, DECIMAL_PLACES)


# --- Main Validation Class ---

class WalletValidation:
    """
    A static class that encapsulates all validation logic for wallet data.

    It provides methods to validate entire wallet objects or individual fields
    against the master schema and business rules. All methods are static,
    ensuring the class remains a stateless, pure validation utility.
    """

    @staticmethod
    def is_valid_wallet_id(wallet_id: str) -> bool:
        """Validates the format of a wallet ID."""
        return _is_valid_format(WalletConfig.WALLET_ID_PATTERN, wallet_id)

    @staticmethod
    def is_valid_eth_address(address: str) -> bool:
        """Validates the format of an Ethereum address."""
        return _is_valid_format(WalletConfig.ADDRESS_PATTERN, address)

    @staticmethod
    def is_valid_hash(hash_str: str) -> bool:
        """Validates the format of a hash string."""
        return _is_valid_format(WalletConfig.HASH_PATTERN, hash_str)

    @staticmethod
    def is_valid_timestamp(timestamp: str) -> bool:
        """Validates if a string is a valid ISO 8601 timestamp."""
        if not isinstance(timestamp, str):
            return False
        try:
            # Handle 'Z' for UTC timezone
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_wallet_data(wallet_data: Dict[str, Any], context: str = "update") -> List[str]:
        """
        Performs a full validation of a wallet data dictionary.

        This is the main entry point for validation, aggregating checks for
        required fields, formats, data types, and business rules.

        Args:
            wallet_data: The dictionary of wallet data to validate.
            context: The operation context ('create', 'update'). This helps
                     tailor validation rules, e.g., for immutable fields.

        Returns:
            A list of string error messages. An empty list indicates success.
        """
        errors = []
        # Create a copy to avoid modifying the original dict during validation
        data_to_validate = wallet_data.copy()

        # 1. Validate required fields for the given context
        errors.extend(WalletValidation._validate_required_fields(data_to_validate, context))

        # 2. Validate formats, types, and values for all present fields
        errors.extend(WalletValidation._validate_field_values(data_to_validate))

        # 3. Validate complex structures like addresses
        errors.extend(WalletValidation._validate_addresses_structure(data_to_validate))

        # 4. Validate business logic and inter-field consistency
        errors.extend(WalletValidation._validate_business_rules(data_to_validate))

        return list(set(errors))  # Return unique errors

    @staticmethod
    def validate_update_data(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> List[str]:
        """
        Validates a proposed update against the current state of a wallet.

        Checks for immutability constraints and then validates the resulting
        merged object.

        Returns:
            A list of validation error messages.
        """
        errors = []

        # 1. Check for attempts to modify immutable fields
        immutable_fields = WalletConfig.get_immutable_fields()
        for field in immutable_fields:
            if field in update_data and update_data[field] != current_data.get(field):
                errors.append(f"Cannot update immutable field: '{field}'")
        if errors:
            return errors

        # 2. Validate the merged data
        merged_data = {**current_data, **update_data}
        errors.extend(WalletValidation.validate_wallet_data(merged_data, context="update"))

        return list(set(errors))

    # --- Private Helper Methods for Validation ---

    @staticmethod
    def _validate_required_fields(wallet_data: Dict[str, Any], context: str) -> List[str]:
        """
        Checks if all required fields are present and not empty.
        For creation, all required fields in the master schema must be present.
        For updates, we only check the fields being provided.
        """
        errors = []
        required_fields = WalletConfig.get_required_fields() if context == "create" else []

        for field in required_fields:
            if wallet_data.get(field) is None or wallet_data.get(field) == "":
                errors.append(f"Missing required field: '{field}'")
        return errors

    @staticmethod
    def _validate_field_values(wallet_data: Dict[str, Any]) -> List[str]:
        """
        Iterates through wallet data and validates each field's value and format.
        """
        errors = []
        for field, value in wallet_data.items():
            # Skip validation for None values unless the field is required (handled elsewhere)
            if value is None:
                continue

            constraints = WalletConfig.get_field_constraints(field)
            if not constraints:
                continue  # No rules for this field

            # Type check
            expected_type = constraints.get("type")
            if expected_type and not isinstance(value, expected_type):
                errors.append(f"Field '{field}' must be of type {expected_type}, but got {type(value)}")
                continue  # Stop further checks if type is wrong

            # Allowed values check
            allowed = constraints.get("allowed_values", [])
            if allowed and value not in allowed:
                errors.append(f"Field '{field}' has an invalid value: '{value}'")

            # Format check (for strings)
            format_pattern = constraints.get("format")
            if format_pattern:
                validators: Dict[str, Callable[[str], bool]] = {
                    "wallet_id": WalletValidation.is_valid_wallet_id,
                    "user_id": is_valid_user_id, # Use the imported function
                    "hash": WalletValidation.is_valid_hash,
                    "iso8601": WalletValidation.is_valid_timestamp,
                }
                if format_pattern in validators and not validators[format_pattern](value):
                    errors.append(f"Invalid format for field '{field}'")

            # Numeric range check
            if isinstance(value, (int, float)):
                min_val = constraints.get("min_value")
                max_val = constraints.get("max_value")
                if min_val is not None and value < min_val:
                    errors.append(f"Field '{field}' is below the minimum value of {min_val}")
                if max_val is not None and value > max_val:
                    errors.append(f"Field '{field}' is above the maximum value of {max_val}")

        return errors

    @staticmethod
    def _validate_addresses_structure(wallet_data: Dict[str, Any]) -> List[str]:
        """Validates the 'addresses' dictionary structure and contained addresses."""
        errors = []
        addresses = wallet_data.get("addresses")
        if not addresses or not isinstance(addresses, dict):
            # If addresses are missing, the required field check will catch it.
            # This check is for structure if the field is present.
            if addresses is not None:
                errors.append("'addresses' field must be a non-empty dictionary")
            return errors

        for addr_type, addr_info in addresses.items():
            if not isinstance(addr_info, dict) or "address" not in addr_info:
                errors.append(f"Address entry for '{addr_type}' is malformed")
                continue
            if not WalletValidation.is_valid_eth_address(addr_info["address"]):
                errors.append(f"Invalid Ethereum address format for type '{addr_type}'")
        return errors

    @staticmethod
    def _validate_business_rules(wallet_data: Dict[str, Any]) -> List[str]:
        """Validates ETH-specific business logic and consistency rules."""
        errors = []
        account_type = wallet_data.get("account_type")
        status = wallet_data.get("status")

        # Rule: Contract accounts must have a code_hash
        if account_type == AccountType.CONTRACT.value and not wallet_data.get("code_hash"):
            errors.append("Contract accounts must have a 'code_hash'")

        # Rule: EOA accounts should not have contract-specific fields
        if account_type == AccountType.EOA.value:
            if wallet_data.get("code_hash"):
                errors.append("EOA accounts should not have a 'code_hash'")
            if wallet_data.get("storage_root"):
                errors.append("EOA accounts should not have a 'storage_root'")

        # Rule: Suspended or deleted wallets should have a zero balance
        if status in [WalletStatus.DELETED.value, WalletStatus.SUSPENDED.value]:
            if wallet_data.get("balance", 0) != 0:
                errors.append(f"Wallets with status '{status}' must have a zero balance")

        return errors

    # --- Transaction-specific Validation ---

    @staticmethod
    def validate_transaction_params(from_address: str, to_address: str, amount: float) -> List[str]:
        """Validates parameters for a standard transfer operation."""
        errors = []
        if not WalletValidation.is_valid_eth_address(from_address):
            errors.append("Invalid 'from_address' format")
        if not WalletValidation.is_valid_eth_address(to_address):
            errors.append("Invalid 'to_address' format")
        if from_address == to_address:
            errors.append("Sender and receiver addresses cannot be the same")
        if not isinstance(amount, (int, float)) or amount <= 0:
            errors.append("Transaction amount must be a positive number")
        if amount > WalletConfig.MAX_BALANCE:
            errors.append(f"Amount exceeds maximum allowed balance of {WalletConfig.MAX_BALANCE}")
        if _format_balance(amount) != amount:
            errors.append(f"Amount precision exceeds the allowed {WalletConfig.PRECISION_DECIMALS} decimals")
        return errors


if __name__ == "__main__":
    """A simple smoke test for the WalletValidation service."""
    print("--- Running wallet_validation.py Smoke Test ---")

    # A valid wallet payload for creation context
    valid_payload = {
        "wallet_id": "W_a94d9554fa3dfe35", # Updated to new format
        "user_id": "U_a94d9554fa3dfe35", # Updated to new format
        "name": "My Test Wallet",
        "balance": 100.0,
        "nonce": 1,
        "wallet_type": "default",
        "status": "active",
        "network": "testnet",
        "currency": "BACHI",
        "addresses": {"eoa": {"address": "0x1234567890123456789012345678901234567890"}},
        "created_at": "2023-01-01T00:00:00Z",
        "last_modified": "2023-01-01T00:00:00Z",
    }

    # 1. Test with valid data
    errors = WalletValidation.validate_wallet_data(valid_payload, context="create")
    assert not errors, f"Validation failed for a valid payload: {errors}"
    print("✅ Correctly validated a valid wallet payload.")

    # 2. Test with invalid data
    invalid_payload = valid_payload.copy()
    invalid_payload["wallet_id"] = "invalid-id"
    invalid_payload["balance"] = -50
    invalid_payload["wallet_type"] = "non_existent_type"
    errors = WalletValidation.validate_wallet_data(invalid_payload, context="create")
    assert len(errors) == 3, f"Expected 3 errors, but got {len(errors)}: {errors}"
    print("✅ Correctly detected multiple errors in an invalid payload.")

    # 3. Test for missing required field
    incomplete_payload = valid_payload.copy()
    del incomplete_payload["name"]
    errors = WalletValidation.validate_wallet_data(incomplete_payload, context="create")
    assert "Missing required field: 'name'" in errors, "Failed to detect missing required field."
    print("✅ Correctly identified a missing required field.")

    # 4. Test immutable field update
    update_attempt = {"wallet_id": "W_0987654321098765"}
    errors = WalletValidation.validate_update_data(valid_payload, update_attempt)
    assert "Cannot update immutable field: 'wallet_id'" in errors, "Failed to block immutable field update."
    print("✅ Correctly blocked an update to an immutable field.")

    # 5. Test valid transaction params
    tx_errors = WalletValidation.validate_transaction_params(
        "0x1234567890123456789012345678901234567890",
        "0x0987654321098765432109876543210987654321",
        10.5
    )
    assert not tx_errors, f"Validation failed for valid transaction params: {tx_errors}"
    print("✅ Correctly validated valid transaction parameters.")

    print("\n--- Smoke Test Passed Successfully! ---")
