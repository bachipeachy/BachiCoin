#!/usr/bin/env python3
"""Modern transaction validation - Clean, no backward compatibility.
This module provides a collection of pure, static methods for validating
transaction data against the rules defined in tx_config.
"""

from typing import List, Dict, Any

from BachiCoin.lib_transaction.tx_config import (
    TxConfig, TxType, Priority
)
from BachiCoin.lib_crossmodule.crossmodule_config import NetworkType


# =================== VALIDATION HELPERS ===================


def get_tx_schema_view(view: str) -> Dict[str, Any]:
    """Get schema fields for a specific view from TxConfig."""
    if view not in TxConfig.SCHEMA_VIEWS:
        raise ValueError(f"Unknown schema view: {view}")
    return {k: TxConfig._TX_SCHEMA[k] for k in TxConfig.SCHEMA_VIEWS[view]}


def is_valid_tx_hash(tx_hash: str) -> bool:
    """Validate transaction hash format."""
    return bool(TxConfig.TX_HASH_PATTERN.match(tx_hash or ""))


def is_valid_address(address: str) -> bool:
    """Validate Ethereum address format."""
    return bool(TxConfig.ADDRESS_PATTERN.match(address or ""))


def is_valid_signature(signature: str) -> bool:
    """Validate signature format - supports both ETH and Bitcoin."""
    if not isinstance(signature, str):
        return False
    # ETH format: 0x + 130 hex chars
    if TxConfig.ETH_SIGNATURE_PATTERN.match(signature):
        return True
    # Bitcoin format: Base64 DER
    if TxConfig.BTC_SIGNATURE_PATTERN.match(signature):
        return True
    return False


def get_tx_types() -> List[str]:
    """Get a list of valid transaction types."""
    return [t.value for t in TxType]


def get_priorities() -> List[str]:
    """Get a list of valid priority levels."""
    return [p.value for p in Priority]


def get_networks() -> List[str]:
    """Get a list of valid networks."""
    return [n.value for n in NetworkType.__members__.values()]


# =================== VALIDATION SERVICE ===================

class TxValidation:
    """A collection of pure, static methods for transaction validation."""

    @staticmethod
    def validate_field(field_name: str, value: Any) -> List[str]:
        """Validate a single field against the transaction schema."""
        errors = []
        schema = TxConfig._TX_SCHEMA.get(field_name)
        if not schema:
            return errors  # No validation rules for this field

        # If not required and no value, validation passes
        # NOTE: With required:True for from/to/nonce in schema, this path is less common
        if not schema.get("required") and value is None:
            return errors

        # 1. Required check (only if schema says it's required and value is None/empty)
        # This check is now primarily for fields that are *always* required (e.g., tx_hash, amount)
        # For from/to/nonce/signature, their requirement is handled by validate_structure_by_type
        if schema.get("required") and (value is None or value == ""):
            # Only add error if it's a field not handled by validate_structure_by_type
            # This avoids duplicate errors for from/to/nonce/signature
            if field_name not in ["from_address", "to_address", "nonce", "signature"]:
                errors.append(f"'{field_name}' is required.")

        # If value is None at this point, and it's not a field we validate format/type for when None
        if value is None:
            return errors

        # 2. Type validation
        expected_type = schema.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"'{field_name}' must be of type {expected_type.__name__}, but got {type(value).__name__}.")

        # 3. Constraint validation (for numbers)
        if isinstance(value, (int, float)):
            min_val = schema.get("min_value")
            if min_val is not None and value < min_val:
                errors.append(f"'{field_name}' must be >= {min_val}.")

        # 4. Format validation (for strings)
        format_rule = schema.get("format")
        if format_rule == "tx_hash" and not is_valid_tx_hash(value):
            errors.append(f"'{field_name}' has an invalid transaction hash format.")
        elif format_rule == "address" and not is_valid_address(value):
            errors.append(f"'{field_name}' has an invalid address format.")
        elif format_rule == "signature" and not is_valid_signature(value):
            # Only validate format if a signature is actually provided (not None)
            if value is not None:
                errors.append(f"'{field_name}' has an invalid signature format.")

        return errors

    @staticmethod
    def validate_gas_fees(tx: Dict[str, Any]) -> List[str]:
        """Validate EIP-1559 gas fee logic."""
        errors = []

        max_fee = tx.get("max_fee_per_gas", 0)
        priority_fee = tx.get("max_priority_fee_per_gas", 0)

        # Defensive cast for gas_limit
        raw_gas_limit = tx.get("gas_limit", 0)
        try:
            gas_limit = int(raw_gas_limit)
        except (ValueError, TypeError):
            gas_limit = 0  # force failure below

        # Validate fees
        if not isinstance(max_fee, (int, float)) or max_fee <= 0:
            errors.append("'max_fee_per_gas' must be a positive number.")

        if not isinstance(priority_fee, (int, float)) or priority_fee < 0:
            errors.append("'max_priority_fee_per_gas' must be a non-negative number.")

        if priority_fee > max_fee:
            errors.append("'max_priority_fee_per_gas' cannot exceed 'max_fee_per_gas'.")

        if gas_limit < TxConfig.MIN_GAS_LIMIT:
            errors.append(f"'gas_limit' must be an integer >= {TxConfig.MIN_GAS_LIMIT}.")

        return errors

    @staticmethod
    def validate_enums(tx: Dict[str, Any]) -> List[str]:
        """Validate fields that should match enum values."""
        errors = []
        if tx.get("tx_type") not in get_tx_types():
            errors.append(f"Invalid 'tx_type': {tx.get('tx_type')}. Must be one of {get_tx_types()}.")
        if "priority" in tx and tx["priority"] not in get_priorities():
            errors.append(f"Invalid 'priority': {tx.get('priority')}. Must be one of {get_priorities()}.")
        if tx.get("network") not in get_networks():
            errors.append(f"Invalid 'network': {tx.get('network')}. Must be one of {get_networks()}.")
        return errors

    @staticmethod
    def validate_structure_by_type(tx: Dict[str, Any]) -> List[str]:
        """Validates the presence/absence of fields based on the transaction type."""
        errors = []
        tx_type = tx.get("tx_type")

        from_addr = tx.get("from_address")
        to_addr = tx.get("to_address")
        nonce = tx.get("nonce")
        signature = tx.get("signature")

        # Helper for common checks
        def check_present(field_name, value):
            if value is None:
                errors.append(f"A '{tx_type}' transaction requires a '{field_name}'.")
        def check_absent(field_name, value):
            if value is not None:
                errors.append(f"A '{tx_type}' transaction must not have a '{field_name}'.")

        if tx_type == TxType.MINT.value or tx_type == TxType.REWARD.value or tx_type == TxType.POOL.value:
            check_absent("from_address", from_addr)
            check_present("to_address", to_addr)
            check_absent("nonce", nonce)
            check_absent("signature", signature)

        elif tx_type == TxType.BURN.value:
            check_present("from_address", from_addr)
            check_absent("to_address", to_addr)
            check_present("nonce", nonce)

        elif tx_type == TxType.SLASH.value:
            check_present("from_address", from_addr)
            check_absent("to_address", to_addr)
            check_absent("nonce", nonce)
            check_absent("signature", signature)

        elif tx_type == TxType.TRANSFER.value or tx_type == TxType.STAKE.value or tx_type == TxType.UNSTAKE.value:
            check_present("from_address", from_addr)
            check_present("to_address", to_addr) # For STAKE/UNSTAKE, to_address is typically the staking contract or self
            check_present("nonce", nonce)
            check_present("signature", signature)
            if tx_type == TxType.TRANSFER.value and from_addr == to_addr:
                errors.append("Sender and receiver address cannot be the same for a transfer.")
        
        # Default for other types (e.g., contract calls, governance)
        # Assume from_address, nonce, signature required, to_address optional
        else: # Covers CONTRACT_CALL, CONTRACT_DEPLOY, GOVERNANCE
            check_present("from_address", from_addr)
            check_present("nonce", nonce)
            check_present("signature", signature)
            # to_address is optional for these, so no check here

        return errors

    @staticmethod
    def validate_transaction(tx: Dict[str, Any]) -> List[str]:
        """Run the complete validation pipeline for a transaction."""
        errors = []

        # 1. Validate enums first to ensure we have a valid tx_type
        errors.extend(TxValidation.validate_enums(tx))
        if any("Invalid 'tx_type'" in e for e in errors):
            return errors  # Stop if tx_type is invalid

        # 2. Validate the structure based on the now-known valid tx_type
        errors.extend(TxValidation.validate_structure_by_type(tx))

        # 3. Validate gas fees
        errors.extend(TxValidation.validate_gas_fees(tx))

        # 4. Validate all fields defined in the schema, checking for presence and format
        for field_name in TxConfig._TX_SCHEMA.keys():
            # Only validate fields that are explicitly required or are present in the transaction
            # The 'required' check in validate_field will handle missing required fields
            if TxConfig._TX_SCHEMA[field_name].get("required") or field_name in tx:
                errors.extend(TxValidation.validate_field(field_name, tx.get(field_name)))

        # Return a unique list of errors
        return sorted(list(set(errors)))


if __name__ == '__main__':
    print("--- Smoke Test for tx_validation.py ---")

    base_tx = {
        "chain_id": 1337,
        "tx_version": 0,
        "max_priority_fee_per_gas": 2.0,
        "max_fee_per_gas": 40.0,
        "gas_limit": 21000,
        "amount": 1.0,
        "currency": "BACHI",
        "network": "testnet",
        "tx_hash": "0x" + "f" * 64, # Dummy hash
        "timestamp": "2023-01-01T00:00:00Z",
        "created_at": "2023-01-01T00:00:00Z"
    }
    from_addr = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
    to_addr = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"

    # 1. Test a valid transfer transaction
    print("\n1. Testing a valid transfer transaction...")
    transfer_tx = {**base_tx, "tx_type": TxType.TRANSFER.value, "from_address": from_addr, "to_address": to_addr, "nonce": 0, "signature": "0x" + "f" * 130}
    errors = TxValidation.validate_transaction(transfer_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid transfer transaction passed validation.")

    # 2. Test a valid mint transaction
    print("\n2. Testing a valid mint transaction...")
    mint_tx = {**base_tx, "tx_type": TxType.MINT.value, "to_address": to_addr, "from_address": None, "nonce": None, "signature": None}
    errors = TxValidation.validate_transaction(mint_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid mint transaction passed validation.")

    # 3. Test an invalid mint transaction (with from_address)
    print("\n3. Testing an invalid mint transaction (with from_address)...")
    invalid_mint_tx = mint_tx.copy()
    invalid_mint_tx["from_address"] = from_addr
    errors = TxValidation.validate_transaction(invalid_mint_tx)
    assert any("must not have a 'from_address'" in e for e in errors), "Should have failed due to from_address"
    print(f"   PASS: Correctly identified errors: {errors}")

    # 4. Test a valid burn transaction
    print("\n4. Testing a valid burn transaction...")
    burn_tx = {**base_tx, "tx_type": TxType.BURN.value, "from_address": from_addr, "nonce": 0, "to_address": None, "signature": "0x" + "f" * 130}
    errors = TxValidation.validate_transaction(burn_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid burn transaction passed validation.")

    # 5. Test an invalid burn transaction (with to_address)
    print("\n5. Testing an invalid burn transaction (with to_address)...")
    invalid_burn_tx = burn_tx.copy()
    invalid_burn_tx["to_address"] = to_addr
    errors = TxValidation.validate_transaction(invalid_burn_tx)
    assert any("must not have a 'to_address'" in e for e in errors), "Should have failed due to to_address"
    print(f"   PASS: Correctly identified errors: {errors}")

    # 6. Test invalid transfer (missing to_address)
    print("\n6. Testing an invalid transfer (missing to_address)...")
    invalid_transfer_tx = transfer_tx.copy()
    invalid_transfer_tx["to_address"] = None # Set to None, not delete
    errors = TxValidation.validate_transaction(invalid_transfer_tx)
    assert any("requires a 'to_address'" in e for e in errors), "Should have failed due to missing to_address"
    print(f"   PASS: Correctly identified errors: {errors}")

    # 7. Test invalid transfer (same from_address and to_address)
    print("\n7. Testing an invalid transfer (same from_address and to_address)...")
    invalid_transfer_same_addr_tx = transfer_tx.copy()
    invalid_transfer_same_addr_tx["to_address"] = from_addr
    errors = TxValidation.validate_transaction(invalid_transfer_same_addr_tx)
    assert any("Sender and receiver address cannot be the same for a transfer." in e for e in errors), "Should have failed due to same addresses"
    print(f"   PASS: Correctly identified errors: {errors}")

    # 8. Test a valid reward transaction
    print("\n8. Testing a valid reward transaction...")
    reward_tx = {**base_tx, "tx_type": TxType.REWARD.value, "to_address": to_addr, "from_address": None, "nonce": None, "signature": None}
    errors = TxValidation.validate_transaction(reward_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid reward transaction passed validation.")

    # 9. Test a valid slash transaction
    print("\n9. Testing a valid slash transaction...")
    slash_tx = {**base_tx, "tx_type": TxType.SLASH.value, "from_address": from_addr, "to_address": None, "nonce": None, "signature": None}
    errors = TxValidation.validate_transaction(slash_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid slash transaction passed validation.")

    # 10. Test a valid stake transaction
    print("\n10. Testing a valid stake transaction...")
    stake_tx = {**base_tx, "tx_type": TxType.STAKE.value, "from_address": from_addr, "to_address": to_addr, "nonce": 0, "signature": "0x" + "f" * 130}
    errors = TxValidation.validate_transaction(stake_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid stake transaction passed validation.")

    # 11. Test a valid unstake transaction
    print("\n11. Testing a valid unstake transaction...")
    unstake_tx = {**base_tx, "tx_type": TxType.UNSTAKE.value, "from_address": from_addr, "to_address": to_addr, "nonce": 0, "signature": "0x" + "f" * 130}
    errors = TxValidation.validate_transaction(unstake_tx)
    assert len(errors) == 0, f"Validation failed unexpectedly: {errors}"
    print("   PASS: Valid unstake transaction passed validation.")

    # 12. Test invalid transaction (missing required field tx_version)
    print("\n12. Testing invalid transaction (missing required field tx_version)...")
    invalid_tx_missing_version = {**transfer_tx}
    del invalid_tx_missing_version["tx_version"]
    errors = TxValidation.validate_transaction(invalid_tx_missing_version)
    assert any("'tx_version' is required." in e for e in errors), "Should have failed due to missing tx_version"
    print(f"   PASS: Correctly identified errors: {errors}")

    print("\n--- Smoke Test Passed ---")
