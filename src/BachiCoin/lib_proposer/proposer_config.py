#!/usr/bin/env python3
"""proposer_config.py - This file defines the configuration, constants, data schemas, and statuses"""

from enum import Enum
from typing import Dict, List, Any

PROPOSER_INDEX_KEY = "proposer_index"

# === 2. Proposer Status Enum ===
# Defines the lifecycle of a block proposal duty.
class ProposerStatus(Enum):
    """Lifecycle states for a proposer's duty for a specific slot."""
    AWAITING_DUTY = "awaiting_duty"  # Assigned to propose, slot is in the future.
    PROPOSING = "proposing"          # Actively building a block for the assigned slot.
    PROPOSAL_SUCCESS = "success"     # Successfully proposed a block that was accepted.
    PROPOSAL_MISSED = "missed"       # Failed to propose a block in the assigned slot.
    PROPOSAL_ORPHANED = "orphaned"   # Proposed a block that was not included in the canonical chain.


# === Proposer Configuration Class ===
class ProposerConfig:
    # Proposer Schema - Defines the structure of a proposal record.
    # Each record represents a single slot duty assigned to a validator.
    _PROPOSER_SCHEMA = {
        "proposal_id": {"type": str, "required": True, "immutable": True},  # e.g., "epoch-slot"
        "slot": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "epoch": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "validator_index": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "status": {"type": str, "required": True, "default": ProposerStatus.AWAITING_DUTY.value,
                   "allowed_values": [ps.value for ps in ProposerStatus]},
        "block_hash": {"type": str, "required": False, "default": None},
        "payload_size_bytes": {"type": int, "required": False, "default": 0, "min_value": 0},
        "transaction_count": {"type": int, "required": False, "default": 0, "min_value": 0},
        "proposed_at": {"type": str, "required": False, "format": "iso8601"},
        "error_message": {"type": str, "required": False, "default": None},
    }

    # Schema Views - Defines subsets of the schema for different use cases.
    PROPOSER_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "proposer_full": list(_PROPOSER_SCHEMA.keys()),
        "proposer_duty": ["proposal_id", "slot", "epoch", "validator_index", "status"],
        "proposer_summary": ["proposal_id", "status", "block_hash", "transaction_count"],
    }


# === Schema and Validation Utilities ===

def get_proposer_schema_view(view: str) -> Dict[str, Any]:
    """Gets the schema definition for a specific view."""
    assert view in ProposerConfig.PROPOSER_SCHEMA_VIEWS, f"Unknown proposer schema view: {view}"
    return {k: ProposerConfig._PROPOSER_SCHEMA[k] for k in ProposerConfig.PROPOSER_SCHEMA_VIEWS[view]
            if k in ProposerConfig._PROPOSER_SCHEMA}


def get_proposer_defaults_for_view(view: str) -> Dict[str, Any]:
    """Gets the default values for all fields in a specific view."""
    schema = get_proposer_schema_view(view)
    return {field: config.get("default") for field, config in schema.items() if "default" in config}


def is_valid_proposer_status(status: str) -> bool:
    """Checks if a given string is a valid proposer status."""
    return status in [ps.value for ps in ProposerStatus]

# === Self-Contained Unit Test ===

if __name__ == "__main__":
    """Unit test for the self-contained proposer_config.py module."""

    print("=== Proposer Configuration Test ===")
    # Test ProposerStatus Enum
    print("\n🧪 Testing ProposerStatus Enum...")
    print(f"   - All Statuses: {[s.value for s in ProposerStatus]}")
    assert ProposerStatus.PROPOSAL_SUCCESS.value == "success"

    # Test schema views
    print("\n🧪 Testing schema views...")
    duty_schema = get_proposer_schema_view("proposer_duty")
    print(f"   - Duty Schema fields: {list(duty_schema.keys())}")
    assert "validator_index" in duty_schema and "block_hash" not in duty_schema

    # Test defaults
    print("\n🧪 Testing default values...")
    duty_defaults = get_proposer_defaults_for_view("proposer_duty")
    print(f"   - Duty Defaults: {duty_defaults}")
    assert duty_defaults.get("status") == ProposerStatus.AWAITING_DUTY.value

    # Test validation utilities
    print("\n🧪 Testing validation utilities...")
    print(f"   - Is 'success' a valid status? {is_valid_proposer_status('success')}")
    print(f"   - Is 'failed' a valid status? {not is_valid_proposer_status('failed')}")
    assert is_valid_proposer_status("missed") and not is_valid_proposer_status("waiting")

    print("\n✅ Proposer Configuration Test Complete!")