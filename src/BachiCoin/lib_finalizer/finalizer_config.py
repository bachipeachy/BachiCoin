#!/usr/bin/env python3
"""finalizer_config.py - This file defines the configuration, constants, data schemas, and statuses"""

from enum import Enum
from typing import Dict, List, Any

FINALIZER_INDEX_KEY = "finalizer_index"

# === Finality Status Enum ===
# Defines the states of a checkpoint in the finalization process.
class FinalityStatus(Enum):
    """Lifecycle states for a checkpoint's finality."""
    JUSTIFIED = "justified"  # Checkpoint has supermajority support.
    FINALIZED = "finalized"  # A subsequent checkpoint has been justified.

# === Finalizer Configuration Class ===
# Contains constants and the data schema for checkpoint records.
class FinalizerConfig:
    # Finality Schema - Defines the structure of a checkpoint record.
    # Each record represents the state of an epoch's checkpoint.
    _CHECKPOINT_SCHEMA = {
        "epoch": {"type": int, "required": True, "min_value": 0, "immutable": True},
        "root": {"type": str, "required": True, "immutable": True},  # Block root of the checkpoint
        "status": {"type": str, "required": True, "default": FinalityStatus.JUSTIFIED.value,
                   "allowed_values": [s.value for s in FinalityStatus]},
        "total_voting_stake": {"type": int, "required": False, "default": 0, "min_value": 0},
        "participating_stake": {"type": int, "required": False, "default": 0, "min_value": 0},
        "justified_at": {"type": str, "required": False, "format": "iso8601"},
        "finalized_at": {"type": str, "required": False, "format": "iso8601"},
    }

    # Schema Views - Defines subsets of the schema for different use cases.
    CHECKPOINT_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "checkpoint_full": list(_CHECKPOINT_SCHEMA.keys()),
        "checkpoint_summary": ["epoch", "root", "status"],
    }

# === Schema and Validation Utilities ===

def get_checkpoint_schema_view(view: str) -> Dict[str, Any]:
    """Gets the schema definition for a specific view."""
    assert view in FinalizerConfig.CHECKPOINT_SCHEMA_VIEWS, f"Unknown checkpoint schema view: {view}"
    return {k: FinalizerConfig._CHECKPOINT_SCHEMA[k] for k in FinalizerConfig.CHECKPOINT_SCHEMA_VIEWS[view]
            if k in FinalizerConfig._CHECKPOINT_SCHEMA}

def get_checkpoint_defaults_for_view(view: str) -> Dict[str, Any]:
    """Gets the default values for all fields in a specific view."""
    schema = get_checkpoint_schema_view(view)
    return {field: config.get("default") for field, config in schema.items() if "default" in config}

def is_valid_finality_status(status: str) -> bool:
    """Checks if a given string is a valid finality status."""
    return status in [s.value for s in FinalityStatus]

# === Self-Contained Unit Test ===

if __name__ == "__main__":
    """Unit test for the self-contained finalizer_config.py module."""
    print("=== Finalizer Configuration Test ===")

    # Test FinalityStatus Enum
    print("\n🧪 Testing FinalityStatus Enum...")
    print(f"   - All Statuses: {[s.value for s in FinalityStatus]}")
    assert FinalityStatus.FINALIZED.value == "finalized"

    # Test schema views
    print("\n🧪 Testing schema views...")
    summary_schema = get_checkpoint_schema_view("checkpoint_summary")
    print(f"   - Summary Schema fields: {list(summary_schema.keys())}")
    assert "epoch" in summary_schema and "justified_at" not in summary_schema

    # Test defaults
    print("\n🧪 Testing default values...")
    full_defaults = get_checkpoint_defaults_for_view("checkpoint_full")
    print(f"   - Full Defaults: {full_defaults}")
    assert full_defaults.get("status") == FinalityStatus.JUSTIFIED.value

    # Test validation utilities
    print("\n🧪 Testing validation utilities...")
    print(f"   - Is 'justified' a valid status? {is_valid_finality_status('justified')}")
    print(f"   - Is 'pending' a valid status? {not is_valid_finality_status('pending')}")
    assert is_valid_finality_status("finalized") and not is_valid_finality_status("waiting")

    print("\n✅ Finalizer Configuration Test Complete!")