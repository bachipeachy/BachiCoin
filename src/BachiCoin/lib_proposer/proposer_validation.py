#!/usr/bin/env python3
"""proposer_validation.py - Pure validation logic for proposer data.

This module provides static methods for validating proposer-related data
structures against the schemas and rules defined in proposer_config.py.
It is designed to be self-contained and free of side effects.
"""

from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from BachiCoin.lib_proposer.proposer_config import ProposerConfig
from BachiCoin.lib_validator.validator_config import ValidatorStatus, ValidatorConfig
from BachiCoin.lib_blockchain.blockchain_config import get_block_schema_view
from BachiCoin.lib_transaction.tx_validation import TxValidation


class ProposerValidation:
    """Pure proposer validation logic, implemented as static methods."""

    @staticmethod
    def validate_field_by_schema(field_name: str, value: Any) -> List[str]:
        """Validates a single field against the proposer schema."""
        errors = []
        constraints = ProposerConfig._PROPOSER_SCHEMA.get(field_name)

        if not constraints:
            return errors

        if constraints.get("required") and (value is None or value == ""):
            errors.append(f"'{field_name}' is required.")
            return errors

        if value is None:
            return errors

        expected_type = constraints.get("type")
        if expected_type and not isinstance(value, expected_type):
            errors.append(
                f"'{field_name}' must be of type {expected_type.__name__}, but got {type(value).__name__}."
            )
            return errors

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
    def validate_proposal_data(proposal_data: Dict[str, Any]) -> List[str]:
        """Performs a full validation of a proposal data dictionary."""
        errors = []
        for field, value in proposal_data.items():
            if field in ProposerConfig._PROPOSER_SCHEMA:
                errors.extend(ProposerValidation.validate_field_by_schema(field, value))

        if "proposal_id" in proposal_data and "epoch" in proposal_data and "slot" in proposal_data:
            expected_id = f"{proposal_data['epoch']}-{proposal_data['slot']}"
            if proposal_data["proposal_id"] != expected_id:
                errors.append(
                    f"Inconsistent 'proposal_id': expected '{expected_id}', got '{proposal_data['proposal_id']}'."
                )
        return errors

    @staticmethod
    def validate_for_creation(proposal_data: Dict[str, Any]) -> List[str]:
        """Validates data specifically for creating a new proposal record."""
        errors = []
        required_fields = [k for k, v in ProposerConfig._PROPOSER_SCHEMA.items() if v.get("required")]
        for field in required_fields:
            if field not in proposal_data or proposal_data.get(field) is None:
                errors.append(f"Missing required field for creation: '{field}'.")
        
        if not errors:
            errors.extend(ProposerValidation.validate_proposal_data(proposal_data))
        return errors

    @staticmethod
    def validate_for_update(update_data: Dict[str, Any]) -> List[str]:
        """Validates data for an update, checking for immutable fields."""
        errors = []
        immutable_fields = [k for k, v in ProposerConfig._PROPOSER_SCHEMA.items() if v.get("immutable")]
        for field in immutable_fields:
            if field in update_data:
                errors.append(f"Cannot update immutable field: '{field}'.")
        for field, value in update_data.items():
            if field in ProposerConfig._PROPOSER_SCHEMA:
                errors.extend(ProposerValidation.validate_field_by_schema(field, value))
        return errors

def assert_valid_for_creation(proposal_data: Dict[str, Any]) -> None:
    """Asserts that proposal data is valid for creation."""
    errors = ProposerValidation.validate_for_creation(proposal_data)
    assert not errors, f"Proposal creation validation failed: {errors}"

def assert_valid_for_update(update_data: Dict[str, Any]) -> None:
    """Asserts that update data is valid."""
    errors = ProposerValidation.validate_for_update(update_data)
    assert not errors, f"Proposal update validation failed: {errors}"

# === Stage 1: Block Proposal Validation

def validate_candidate_block(
    candidate_block: Dict[str, Any],
    get_validator_func: Callable[[int], Optional[Dict[str, Any]]],
    get_chain_tip_func: Callable[[], Optional[Dict[str, Any]]],
) -> List[str]:
    """
    Validates a candidate block at the moment of its creation by a proposer.
    This is the first stage of block validation.

    Args:
        candidate_block: The block data being proposed.
        get_validator_func: A callable function to fetch validator information.
        get_chain_tip_func: A callable function to fetch the current chain tip.

    Returns:
        A list of validation error strings. An empty list means the block is valid.
    """
    errors = []
    header = candidate_block.get("header", {})
    body = candidate_block.get("body", {})

    proposer_index = header.get("proposer_index")
    proposer_validator = get_validator_func(proposer_index) # Use callable

    # 1. Proposer Eligibility
    if not proposer_validator:
        errors.append(f"Proposer validator record not found for index {proposer_index}.")
        return errors  # Cannot proceed without the proposer's data

    if proposer_validator.get("status") != ValidatorStatus.ACTIVE_ONGOING.value:
        errors.append(f"Proposer {proposer_index} is not an active validator.")
    if proposer_validator.get("effective_balance", 0) < ValidatorConfig.MIN_DEPOSIT_AMOUNT:
        errors.append(f"Proposer {proposer_index} has insufficient stake.")

    # 2. Slot Correctness
    parent_block = get_chain_tip_func() # Use callable
    if not parent_block:
        # This can happen for the genesis block, but build_candidate_block should not be called for genesis.
        errors.append("Could not retrieve parent block (chain tip).")
        return errors
        
    block_slot = header.get("slot")
    parent_slot = parent_block.get("header", {}).get("slot", -1)
    if block_slot is None or block_slot <= parent_slot:
        errors.append(f"Invalid slot: block slot ({block_slot}) must be greater than parent slot ({parent_slot}).")

    # 3. Block Structure Completeness (Corrected)
    create_schema_fields = get_block_schema_view("create")
    for field in create_schema_fields:
        if field in ["transactions"]:
            if field not in body:
                errors.append(f"Missing required field in block body: '{field}'.")
        elif field in ["block_type"]:
            if field not in candidate_block:
                errors.append(f"Missing required top-level field in block: '{field}'.")
        else: # All other fields should be in the header
            if field not in header:
                errors.append(f"Missing required field in block header: '{field}'.")

    # 4. RANDAO Reveal Presence (Signature validation is a consensus-level task)
    if "randao_reveal" not in header:
        errors.append("Candidate block header is missing 'randao_reveal' field.")

    # 5. Transaction Set Validity (Delegated to TxValidation)
    transactions = body.get("transactions", [])
    if not isinstance(transactions, list):
        errors.append("'transactions' field must be a list.")
    else:
        for i, tx in enumerate(transactions):
            tx_errors = TxValidation.validate_transaction(tx)
            if tx_errors:
                errors.append(f"Transaction at index {i} ({tx.get('tx_hash', 'N/A')[:10]}...) failed validation: {tx_errors}")

    return errors

if __name__ == "__main__":
    """Unit test for the proposer_validation module."""
    print("=== Proposer Validation Test ===")

    valid_proposal = {
        "proposal_id": "10-320", "slot": 320, "epoch": 10, "validator_index": 123,
        "status": "awaiting_duty",
    }
    print("\n🧪 1. Testing a valid proposal record for creation...")
    assert_valid_for_creation(valid_proposal)
    print("✅ PASSED: Valid proposal data is accepted.")

    print("\n🧪 2. Testing invalid data scenarios...")
    invalid_tests = {
        "Missing 'validator_index'": ("validator_index", None),
        "Incorrect type for 'slot'": ("slot", "not-a-number"),
        "Negative 'payload_size_bytes'": ("payload_size_bytes", -100),
        "Invalid 'status'": ("status", "on_vacation"),
        "Inconsistent 'proposal_id'": ("proposal_id", "11-321"),
    }
    for name, (field, value) in invalid_tests.items():
        test_data = valid_proposal.copy()
        if value is None: del test_data[field]
        else: test_data[field] = value
        errors = ProposerValidation.validate_for_creation(test_data)
        print(f"   - {name}: {'PASSED' if errors else 'FAILED'}")
        assert errors, f"Test '{name}' should have failed but passed."

    print("\n🧪 3. Testing update validation...")
    valid_update = {"status": "success", "block_hash": "0x" + "a" * 64}
    assert_valid_for_update(valid_update)
    print("   - Valid update data: PASSED")

    invalid_update = {"status": "missed", "slot": 999}
    errors_update = ProposerValidation.validate_for_update(invalid_update)
    print(f"   - Immutable field update: {'PASSED' if errors_update else 'FAILED'}")
    assert "Cannot update immutable field: 'slot'" in errors_update[0]

    print("\n✅ Proposer Validation Test Complete!")
