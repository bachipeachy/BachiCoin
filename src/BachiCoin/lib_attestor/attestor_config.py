#!/usr/bin/env python3
"""attestor_config.py - Attestor module configuration

This file defines the configuration, constants, data schemas, and statuses
for the attestation module, following the self-contained, unshackled
design pattern.
"""

from enum import Enum
from typing import Dict, List, Any

ATTESTOR_INDEX_KEY = "attestor_index"

# === Attestation Status Enum ===
# Defines the lifecycle of an attestation duty.
class AttestorStatus(Enum):
    """Lifecycle states for a validator's attestation duty."""
    AWAITING_DUTY = "awaiting_duty"          # Assigned to attest, slot is in the future.
    AWAITING_INCLUSION = "awaiting_inclusion"  # Attestation broadcasted, waiting for inclusion.
    INCLUDED_SUCCESS = "included_success"    # Attestation included successfully on-chain.
    INCLUDED_LATE = "included_late"          # Attestation included, but after the optimal window.
    MISSED = "missed"                        # Failed to produce an attestation for the assigned slot.
    ORPHANED = "orphaned"                    # Included in a non-canonical (orphaned) block.


# === Attestor Configuration Class ===
# Contains constants and the data schema for attestation records.
class AttestorConfig:
    # Attestation Schema - Defines the structure of an attestation record.
    # Each record represents a single attestation duty for a validator.
    _ATTESTOR_SCHEMA = {
        "attestation_id": {"type": str, "required": True, "immutable": True},  # e.g., "slot-validator_index"
        "slot": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "epoch": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "validator_index": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "committee_index": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "status": {"type": str, "required": True, "default": AttestorStatus.AWAITING_DUTY.value,
                   "allowed_values": [s.value for s in AttestorStatus]},
        "data_root": {"type": str, "required": False, "default": None},
        "target_epoch": {"type": int, "required": False, "min_value": 0},
        "target_root": {"type": str, "required": False, "default": None},
        "source_epoch": {"type": int, "required": False, "min_value": 0},
        "source_root": {"type": str, "required": False, "default": None},
        "inclusion_slot": {"type": int, "required": False, "min_value": 0},
        "inclusion_delay": {"type": int, "required": False, "min_value": 0},
        "created_at": {"type": str, "required": False, "format": "iso8601"},
    }

    # Schema Views - Defines subsets of the schema for different use cases.
    ATTESTOR_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "attestation_full": list(_ATTESTOR_SCHEMA.keys()),
        "attestation_duty": ["attestation_id", "slot", "epoch", "validator_index", "committee_index", "status"],
        "attestation_summary": ["attestation_id", "status", "inclusion_slot", "inclusion_delay"],
    }

# === Schema and Validation Utilities ===

def get_attestor_schema_view(view: str) -> Dict[str, Any]:
    """Gets the schema definition for a specific view."""
    assert view in AttestorConfig.ATTESTOR_SCHEMA_VIEWS, f"Unknown attestor schema view: {view}"
    return {k: AttestorConfig._ATTESTOR_SCHEMA[k] for k in AttestorConfig.ATTESTOR_SCHEMA_VIEWS[view]
            if k in AttestorConfig._ATTESTOR_SCHEMA}

def get_attestor_defaults_for_view(view: str) -> Dict[str, Any]:
    """Gets the default values for all fields in a specific view."""
    schema = get_attestor_schema_view(view)
    return {field: config.get("default") for field, config in schema.items() if "default" in config}

def is_valid_attestation_status(status: str) -> bool:
    """Checks if a given string is a valid attestation status."""
    return status in [s.value for s in AttestorStatus]

# === Self-Contained Unit Test ===

if __name__ == "__main__":
    """Unit test for the self-contained attestor_config.py module."""
    print("=== Attestor Configuration Test ===")

    # Test AttestorStatus Enum
    print("\n🧪 Testing AttestorStatus Enum...")
    print(f"   - All Statuses: {[s.value for s in AttestorStatus]}")
    assert AttestorStatus.INCLUDED_SUCCESS.value == "included_success"

    # Test schema views
    print("\n🧪 Testing schema views...")
    duty_schema = get_attestor_schema_view("attestation_duty")
    print(f"   - Duty Schema fields: {list(duty_schema.keys())}")
    assert "committee_index" in duty_schema and "data_root" not in duty_schema

    # Test defaults
    print("\n🧪 Testing default values...")
    duty_defaults = get_attestor_defaults_for_view("attestation_duty")
    print(f"   - Duty Defaults: {duty_defaults}")
    assert duty_defaults.get("status") == AttestorStatus.AWAITING_DUTY.value

    # Test validation utilities
    print("\n🧪 Testing validation utilities...")
    print(f"   - Is 'missed' a valid status? {is_valid_attestation_status('missed')}")
    print(f"   - Is 'failed' a valid status? {not is_valid_attestation_status('failed')}")
    assert is_valid_attestation_status("orphaned") and not is_valid_attestation_status("waiting")

    print("\n✅ Attestor Configuration Test Complete!")