#!/usr/bin/env python3
"""Blockchain validation helper - EIP-1559 aligned, KISS design
CLEAN: Pure validation only, aligned with modernized blockchain_config
"""

import time
from typing import Dict, List, Any

from BachiCoin.lib_blockchain.blockchain_config import (
    BlockchainConfig,
    is_valid_block_hash,
    is_valid_merkle_root,
    is_valid_verkle_root,
    is_valid_block_type,
    is_valid_network_type,
    is_valid_block_status,
    is_valid_consensus_type,
    MAX_TIMESTAMP_DRIFT
)

class BlockchainValidation:
    """Pure blockchain validation - EIP-1559 aligned, static methods only"""

    @staticmethod
    def _get_field_from_block(block_data: Dict[str, Any], field_name: str) -> Any:
        """Helper to get a field from the correct location (header, body, or root)."""
        header = block_data.get("header", {})
        body = block_data.get("body", {})
        if field_name in header:
            return header.get(field_name)
        if field_name in body:
            return body.get(field_name)
        return block_data.get(field_name)

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validate field using schema constraints"""
        errors = []
        constraints = BlockchainConfig.get_field_constraints(field_name)

        if not constraints:
            return errors

        # Required check
        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"{field_name} is required")
            return errors

        if value is None:
            return errors

        # Type check
        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            # Handle tuple types (int, float)
            if isinstance(expected_type, tuple):
                if not any(isinstance(value, t) for t in expected_type):
                    type_names = [t.__name__ for t in expected_type]
                    errors.append(f"{field_name} must be one of {type_names}")
            else:
                errors.append(f"{field_name} must be {expected_type.__name__}")

        # String validations
        if isinstance(value, str):
            # Length checks
            if "min_length" in constraints and len(value.strip()) < constraints["min_length"]:
                errors.append(f"{field_name} too short")
            if "max_length" in constraints and len(value) > constraints["max_length"]:
                errors.append(f"{field_name} too long")

        # Bytes validations
        if isinstance(value, bytes):
            if "max_length" in constraints and len(value) > constraints["max_length"]:
                errors.append(f"{field_name} exceeds max length")

        # Numeric validations
        if isinstance(value, (int, float)):
            if "min_value" in constraints and value < constraints["min_value"]:
                errors.append(f"{field_name} below minimum")
            if "max_value" in constraints and value > constraints["max_value"]:
                errors.append(f"{field_name} above maximum")

        # Allowed values check
        allowed = constraints.get("allowed_values", [])
        if allowed and value not in allowed:
            errors.append(f"{field_name} not in allowed values")

        return errors

    @staticmethod
    def validate_required_fields(block_data: Dict[str, Any], view: str = None) -> List[str]:
        """Validate required fields for specific view, aware of block structure."""
        errors = []
        config = BlockchainConfig()
        required_fields = config.get_required_fields(view)
        
        for field in required_fields:
            value = BlockchainValidation._get_field_from_block(block_data, field)
            if value is None or value == "":
                errors.append(f"Missing required field: {field}")
        
        return errors

    @staticmethod
    def validate_field_formats(block_data: Dict[str, Any]) -> List[str]:
        """Validate field formats and values, aware of block structure."""
        errors = []
        
        # Helper to get value and add error if format is invalid
        def check_format(field, validator, error_msg):
            value = BlockchainValidation._get_field_from_block(block_data, field)
            if value and not validator(value):
                errors.append(error_msg)

        check_format("block_hash", is_valid_block_hash, "Invalid block_hash format")
        check_format("parent_hash", is_valid_block_hash, "Invalid parent_hash format")
        check_format("state_root", is_valid_verkle_root, "Invalid state_root format")
        check_format("transactions_root", is_valid_merkle_root, "Invalid transactions_root format")
        check_format("receipts_root", is_valid_merkle_root, "Invalid receipts_root format")
        check_format("mix_hash", is_valid_block_hash, "Invalid mix_hash format")
        
        block_type = BlockchainValidation._get_field_from_block(block_data, "block_type")
        if block_type and not is_valid_block_type(block_type):
            errors.append(f"Invalid block_type: {block_type}")

        network = BlockchainValidation._get_field_from_block(block_data, "network")
        if network and not is_valid_network_type(network):
            errors.append(f"Invalid network: {network}")

        status = BlockchainValidation._get_field_from_block(block_data, "status")
        if status and not is_valid_block_status(status):
            errors.append(f"Invalid status: {status}")

        consensus_type = BlockchainValidation._get_field_from_block(block_data, "consensus_type")
        if consensus_type and not is_valid_consensus_type(consensus_type):
            errors.append(f"Invalid consensus_type: {consensus_type}")

        return errors

    @staticmethod
    def validate_eip1559_gas_fields(block_data: Dict[str, Any]) -> List[str]:
        """Validate EIP-1559 gas-related fields, aware of block structure."""
        errors = []
        
        gas_limit = BlockchainValidation._get_field_from_block(block_data, "gas_limit") or 0
        gas_used = BlockchainValidation._get_field_from_block(block_data, "gas_used") or 0
        base_fee = BlockchainValidation._get_field_from_block(block_data, "base_fee_per_gas") or 0
        
        if gas_used > gas_limit:
            errors.append("gas_used exceeds gas_limit")
        if base_fee < BlockchainConfig.MIN_BASE_FEE:
            errors.append(f"base_fee_per_gas below minimum: {BlockchainConfig.MIN_BASE_FEE}")
        if gas_limit < BlockchainConfig.MIN_GAS_LIMIT:
            errors.append(f"gas_limit below minimum: {BlockchainConfig.MIN_GAS_LIMIT}.")
        if gas_limit > BlockchainConfig.MAX_GAS_LIMIT:
            errors.append(f"gas_limit above maximum: {BlockchainConfig.MAX_GAS_LIMIT}.")
        
        return errors

    @staticmethod
    def validate_consensus_fields(block_data: Dict[str, Any]) -> List[str]:
        """Validate consensus-specific fields, aware of block structure."""
        errors = []
        
        consensus_type = BlockchainValidation._get_field_from_block(block_data, "consensus_type") or "proof_of_stake"
        
        if consensus_type == "proof_of_stake":
            required_pos_fields = ["slot", "epoch", "proposer_index"]
            for field in required_pos_fields:
                value = BlockchainValidation._get_field_from_block(block_data, field)
                if value is None:
                    errors.append(f"PoS block missing required field: {field}.")
                elif isinstance(value, int) and value < 0:
                    errors.append(f"PoS field {field} must be non-negative.")
        
        elif consensus_type in ["proof_of_work", "hybrid"]:
            difficulty = BlockchainValidation._get_field_from_block(block_data, "difficulty")
            if difficulty is not None:
                if difficulty < BlockchainConfig.MIN_DIFFICULTY:
                    errors.append(f"difficulty below minimum: {BlockchainConfig.MIN_DIFFICULTY}.")
                if difficulty > BlockchainConfig.MAX_DIFFICULTY:
                    errors.append(f"difficulty above maximum: {BlockchainConfig.MAX_DIFFICULTY}.")
        
        return errors

    @staticmethod
    def validate_timestamp(block_data: Dict[str, Any]) -> List[str]:
        """Validate timestamp constraints, aware of block structure."""
        errors = []
        timestamp = BlockchainValidation._get_field_from_block(block_data, "timestamp")
        height = BlockchainValidation._get_field_from_block(block_data, "height") or 0
        
        if timestamp is None:
            return errors
        
        current_time = int(time.time())
        
        if timestamp > current_time + MAX_TIMESTAMP_DRIFT:
            errors.append(f"Block timestamp too far in future: {timestamp}.")

        if height > 0 and timestamp < 1000000000:
            errors.append(f"Block timestamp too old: {timestamp}.")

        return errors

    @staticmethod
    def validate_transaction_list(block_data: Dict[str, Any]) -> List[str]:
        """Validate transaction list consistency, aware of block structure."""
        errors = []
        
        transactions = BlockchainValidation._get_field_from_block(block_data, "transactions") or []
        transaction_count = BlockchainValidation._get_field_from_block(block_data, "transaction_count") or 0
        
        if len(transactions) != transaction_count:
            errors.append(f"Transaction count mismatch: list has {len(transactions)}, count field has {transaction_count}.")
        
        for i, tx in enumerate(transactions):
            if isinstance(tx, str):
                if not is_valid_block_hash(tx):
                    errors.append(f"Invalid transaction hash format at index {i}.")
            elif isinstance(tx, dict):
                if "tx_hash" not in tx:
                    errors.append(f"Transaction missing tx_hash at index {i}.")
        
        return errors

    @staticmethod
    def validate_block_height_sequence(block_data: Dict[str, Any], parent_height: int = None) -> List[str]:
        """Validate block height sequence, aware of block structure."""
        errors = []
        height = BlockchainValidation._get_field_from_block(block_data, "height")
        
        if height is None:
            return errors
            
        if height == 0:
            parent_hash = BlockchainValidation._get_field_from_block(block_data, "parent_hash")
            if parent_hash != "0x" + "0" * 64:
                errors.append("Genesis block must have null parent hash.")
        else:
            if parent_height is not None:
                expected_height = parent_height + 1
                if height != expected_height:
                    errors.append(f"Invalid height sequence: expected {expected_height}, got {height}.")
        
        return errors

    @staticmethod
    def validate_block_creation_requirements(block_data: Dict[str, Any]) -> List[str]:
        """Validate specific requirements for block creation, aware of block structure."""
        errors = []

        essential_fields = ["parent_hash", "gas_limit", "base_fee_per_gas", "consensus_type"]
        for field in essential_fields:
            if not BlockchainValidation._get_field_from_block(block_data, field):
                errors.append(f"Missing essential field for creation: {field}.")

        block_type = BlockchainValidation._get_field_from_block(block_data, "block_type")
        if block_type == "genesis":
            height = BlockchainValidation._get_field_from_block(block_data, "height") or 0
            parent_hash = BlockchainValidation._get_field_from_block(block_data, "parent_hash")
            if height != 0:
                errors.append("Genesis block height must be 0.")
            if parent_hash != "0x" + "0" * 64:
                errors.append("Genesis block must have null parent hash.")

        return errors

    @staticmethod
    def validate_block_data_basic(block_data: Dict[str, Any], view: str = None) -> List[str]:
        """Main validation function, aware of block structure."""
        errors = []
        
        errors.extend(BlockchainValidation.validate_required_fields(block_data, view))
        errors.extend(BlockchainValidation.validate_field_formats(block_data))
        errors.extend(BlockchainValidation.validate_eip1559_gas_fields(block_data))
        errors.extend(BlockchainValidation.validate_consensus_fields(block_data))
        errors.extend(BlockchainValidation.validate_timestamp(block_data))
        errors.extend(BlockchainValidation.validate_transaction_list(block_data))
        errors.extend(BlockchainValidation.validate_block_height_sequence(block_data))
        
        return errors

    @staticmethod
    def validate_for_creation(block_data: Dict[str, Any]) -> List[str]:
        """Validate for block creation, aware of block structure."""
        errors = BlockchainValidation.validate_block_data_basic(block_data, "create")
        errors.extend(BlockchainValidation.validate_block_creation_requirements(block_data))
        return errors

    @staticmethod
    def validate_for_update(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> List[str]:
        """Validate for block update, aware of block structure."""
        errors = []

        immutable_fields = ["block_hash", "parent_hash", "height", "timestamp", "created_at", "consensus_type"]
        for field in immutable_fields:
            if field in update_data: # Note: update_data is flat, this check is simple
                errors.append(f"Cannot update immutable field: {field}.")

        if update_data:
            merged_data = current_data.copy()
            # This merge is tricky with nested structures. Assuming flat updates for now.
            merged_data.update(update_data)
            errors.extend(BlockchainValidation.validate_block_data_basic(merged_data))

        return errors

# Utility functions for external use - fail-fast with assertions
def assert_valid_block_data(block_data: Dict[str, Any], view: str = None) -> None:
    errors = BlockchainValidation.validate_block_data_basic(block_data, view)
    assert len(errors) == 0, f"Block validation failed: {errors}"

def assert_valid_creation_data(block_data: Dict[str, Any]) -> None:
    errors = BlockchainValidation.validate_for_creation(block_data)
    assert len(errors) == 0, f"Block creation validation failed: {errors}"

def assert_valid_update_data(current_data: Dict[str, Any], update_data: Dict[str, Any]) -> None:
    errors = BlockchainValidation.validate_for_update(current_data, update_data)
    assert len(errors) == 0, f"Block update validation failed: {errors}"

if __name__ == "__main__":
    """EIP-1559 aligned validation testing with dummy data."""
    print("=== Blockchain Validation Smoke Test (Dummy Data) ===")

    # --- Test 1: Valid Block Data ---
    valid_block = {
        "header": {
            "parent_hash": "0x" + "0" * 64, "height": 0, "slot": 0, "epoch": 0,
            "proposer_index": 0, "randao_reveal": "0x" + "b" * 192,
            "state_root": "0x" + "c" * 64, "transactions_root": "0x" + "d" * 64,
            "receipts_root": "0x" + "e" * 64, "gas_limit": 15000000, "gas_used": 0,
            "base_fee_per_gas": 1000000000, "timestamp": int(time.time()),
            "extra_data": b"Genesis Block", "consensus_type": "proof_of_stake",
        },
        "body": { "transactions": [] },
        "block_hash": "0x" + "a" * 64, "block_type": "genesis", "network": "testnet",
        "transaction_count": 0, "status": "finalized",
    }
    errors = BlockchainValidation.validate_block_data_basic(valid_block)
    assert not errors, f"Valid block failed basic validation: {errors}"
    print("✅ Valid block data passed basic validation.")

    errors = BlockchainValidation.validate_for_creation(valid_block)
    assert not errors, f"Valid block failed creation validation: {errors}"
    print("✅ Valid block data passed creation validation.")

    # --- Test 2: Invalid Block Data (Missing required field) ---
    invalid_block_missing_parent = valid_block.copy()
    invalid_block_missing_parent["header"] = invalid_block_missing_parent["header"].copy()
    del invalid_block_missing_parent["header"]["parent_hash"]
    errors = BlockchainValidation.validate_block_data_basic(invalid_block_missing_parent)
    assert any("Missing required field: parent_hash" in e for e in errors), "Should have failed for missing parent_hash."
    print("✅ Invalid block (missing parent_hash) correctly failed validation.")

    # --- Test 3: Invalid Block Data (Invalid hash format) ---
    invalid_block_bad_hash = valid_block.copy()
    invalid_block_bad_hash["block_hash"] = "0x123"
    errors = BlockchainValidation.validate_block_data_basic(invalid_block_bad_hash)
    assert any("Invalid block_hash format" in e for e in errors), "Should have failed for invalid block_hash format."
    print("✅ Invalid block (bad hash format) correctly failed validation.")

    # --- Test 4: Invalid Block Data (Gas used exceeds limit) ---
    invalid_block_gas_exceeds = valid_block.copy()
    invalid_block_gas_exceeds["header"] = invalid_block_gas_exceeds["header"].copy()
    invalid_block_gas_exceeds["header"]["gas_used"] = 20000000
    invalid_block_gas_exceeds["header"]["gas_limit"] = 10000000
    errors = BlockchainValidation.validate_block_data_basic(invalid_block_gas_exceeds)
    assert any("gas_used exceeds gas_limit" in e for e in errors), "Should have failed for gas_used exceeding gas_limit."
    print("✅ Invalid block (gas_used exceeds limit) correctly failed validation.")

    # --- Test 5: Invalid Block Data (Future timestamp) ---
    invalid_block_future_ts = valid_block.copy()
    invalid_block_future_ts["header"] = invalid_block_future_ts["header"].copy()
    invalid_block_future_ts["header"]["timestamp"] = int(time.time()) + MAX_TIMESTAMP_DRIFT + 100
    errors = BlockchainValidation.validate_block_data_basic(invalid_block_future_ts)
    assert any("Block timestamp too far in future" in e for e in errors), "Should have failed for future timestamp."
    print("✅ Invalid block (future timestamp) correctly failed validation.")

    # --- Test 6: Update validation (immutable field) ---
    current_block = valid_block.copy()
    update_attempt = {"height": 1} # This is now in the header
    errors = BlockchainValidation.validate_for_update(current_block, update_attempt)
    assert any("Cannot update immutable field: height" in e for e in errors), "Should have failed for updating immutable field."
    print("✅ Update validation (immutable field) correctly failed.")

    print("\n=== Blockchain Validation Smoke Test Passed Successfully! ===")
