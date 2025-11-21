#!/usr/bin/env python3
"""validator_config.py - Self-contained module configuration, following KISS design."""

import re
from enum import Enum
from typing import Dict, List, Any

VALIDATOR_INDEX_KEY = "validator_index"

# JIT_FIELDS: dynamic, computed during consensus operations (copied for now)
# These fields are typically managed by the consensus layer, but are included
# here for completeness of the validator's own state representation.
JIT_FIELDS = [
    "committee_assignments",    # Calculated per epoch
    "validator_duties",         # Calculated per epoch
    "participation_rates",      # Calculated after attestations
    "finality_epochs",          # Updated during consensus
    "effective_balance",        # Updated per epoch
    "inclusion_delay",          # Calculated during attestation processing
    "attestation_rewards",      # Calculated after epoch
    "proposer_rewards",         # Calculated after block proposal
    "slashing_penalties",       # Applied when slashed
    "last_committee_assignment", # Cached assignment data
    "current_duties",           # Current epoch duties
    "next_duties",              # Next epoch duties
]

class ValidatorStatus(Enum):
    """ETH2 validator lifecycle states"""
    ACTIVE_ONGOING = "active_ongoing"    # Actively validating
    ACTIVE_EXITING = "active_exiting"    # In exit queue
    ACTIVE_SLASHED = "active_slashed"    # Slashed but still active
    PENDING_INITIALIZED = "pending_initialized"  # Deposit received
    PENDING_QUEUED = "pending_queued"    # Waiting for activation
    EXITED_UNSLASHED = "exited_unslashed"  # Clean exit
    EXITED_SLASHED = "exited_slashed"    # Slashed and exited
    WITHDRAWAL_POSSIBLE = "withdrawal_possible"  # Can withdraw
    WITHDRAWAL_DONE = "withdrawal_done"  # Withdrawn

class ValidatorConfig:
    # Validator Requirements (copied from ConsensusConfig)
    MIN_DEPOSIT_AMOUNT = 32_000_000_000   # 32 ETH in wei
    MAX_EFFECTIVE_BALANCE = 32_000_000_000  # 32 ETH cap
    EJECTION_BALANCE = 16_000_000_000     # 16 ETH ejection threshold

    # Validation patterns (copied from ConsensusConfig)
    PUBKEY_PATTERN = re.compile(r'^0x[a-fA-F0-9]{96}$')  # BLS12-381 public key
    # SIGNATURE_PATTERN is not directly used by validator, but part of consensus
    WITHDRAWAL_CREDENTIALS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')

    # Validator Schema - v8 pattern (copied from ConsensusConfig)
    _VALIDATOR_SCHEMA = {
        "validator_index": {"type": int, "required": True, "min_value": 0},
        "pubkey": {"type": str, "required": True, "format": "pubkey", "immutable": True},
        "withdrawal_credentials": {"type": str, "required": True, "format": "withdrawal_credentials"},
        "effective_balance": {"type": int, "required": True, "min_value": 0, "max_value": MAX_EFFECTIVE_BALANCE},
        "slashed": {"type": bool, "required": True, "default": False},
        "activation_eligibility_epoch": {"type": int, "required": True, "default": 2**64 - 1},
        "activation_epoch": {"type": int, "required": True, "default": 2**64 - 1},
        "exit_epoch": {"type": int, "required": True, "default": 2**64 - 1},
        "withdrawable_epoch": {"type": int, "required": True, "default": 2**64 - 1},
        "status": {"type": str, "required": True, "default": ValidatorStatus.PENDING_INITIALIZED.value,
                   "allowed_values": [vs.value for vs in ValidatorStatus]},
        "balance": {"type": int, "required": False, "default": 0, "min_value": 0},
        "last_attestation_slot": {"type": int, "required": False, "default": None},
        "created_at": {"type": str, "required": False, "format": "iso8601"},
        "updated_at": {"type": str, "required": False, "format": "iso8601"},
    }

    # Schema Views - v8 pattern (only validator-specific views)
    VALIDATOR_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "validator_full": list(_VALIDATOR_SCHEMA.keys()),
        "validator_create": ["pubkey", "withdrawal_credentials", "effective_balance"],
        "validator_active": ["validator_index", "pubkey", "effective_balance", "status", "slashed"],
        "validator_duties": ["validator_index", "status", "effective_balance", "last_attestation_slot"],
    }

# Schema utilities
def get_validator_schema_view(view: str) -> Dict[str, Any]:
    """Get schema fields for specific view"""
    assert view in ValidatorConfig.VALIDATOR_SCHEMA_VIEWS, f"Unknown validator schema view: {view}"
    return {k: ValidatorConfig._VALIDATOR_SCHEMA[k] for k in ValidatorConfig.VALIDATOR_SCHEMA_VIEWS[view]
            if k in ValidatorConfig._VALIDATOR_SCHEMA}

def get_validator_defaults_for_view(view: str) -> Dict[str, Any]:
    """Get default values for specific view"""
    schema = get_validator_schema_view(view)
    return {field: config.get("default") for field, config in schema.items()
            if "default" in config}

def get_validator_full_defaults() -> Dict[str, Any]:
    """Get full default values for all validator fields with JIT handling"""
    defaults = {}
    for field, config in ValidatorConfig._VALIDATOR_SCHEMA.items():
        if field in JIT_FIELDS: # Use the JIT_FIELDS defined in this module
            defaults[field] = None
        elif "default" in config:
            defaults[field] = config["default"]
        else:
            field_type = config.get("type", str)
            if field_type == str:
                defaults[field] = None
            elif field_type in (int, float):
                defaults[field] = 0.0 if field_type == float else 0
            elif field_type == bool:
                defaults[field] = False
            elif field_type == list:
                defaults[field] = []
            else:
                defaults[field] = None
    return defaults

# Validation utilities
def is_valid_pubkey(pubkey: str) -> bool:
    """Validate BLS12-381 public key format"""
    return bool(ValidatorConfig.PUBKEY_PATTERN.match(pubkey or ""))

def is_valid_withdrawal_credentials(credentials: str) -> bool:
    """Validate withdrawal credentials format"""
    return bool(ValidatorConfig.WITHDRAWAL_CREDENTIALS_PATTERN.match(credentials or ""))

def is_valid_validator_status(status: str) -> bool:
    """Validate validator status"""
    return status in [vs.value for vs in ValidatorStatus]

if __name__ == "__main__":
    """Test validator_config.py - self-contained module config"""
    print("=== Validator Configuration Test ===")

    print(f"Validator Index KEY: {VALIDATOR_INDEX_KEY}")

    # Test ValidatorStatus Enum
    print(f"\nValidator Statuses: {[s.value for s in ValidatorStatus]}")
    assert ValidatorStatus.ACTIVE_ONGOING.value == "active_ongoing"

    # Test JIT_FIELDS
    print(f"\nJIT Fields: {JIT_FIELDS}")

    # Test ValidatorConfig constants
    print(f"\nMin Deposit Amount: {ValidatorConfig.MIN_DEPOSIT_AMOUNT}")
    print(f"Max Effective Balance: {ValidatorConfig.MAX_EFFECTIVE_BALANCE}")

    # Test schema views
    full_schema = get_validator_schema_view("validator_full")
    print(f"\nValidator Full Schema fields: {list(full_schema.keys())}")
    assert "pubkey" in full_schema
    assert "status" in full_schema

    create_schema = get_validator_schema_view("validator_create")
    print(f"Validator Create Schema fields: {list(create_schema.keys())}")
    assert "pubkey" in create_schema
    assert "status" not in create_schema # status is default

    # Test defaults
    full_defaults = get_validator_full_defaults()
    print(f"\nValidator Full Defaults (sample):")
    print(f"  status: {full_defaults.get('status')}")
    print(f"  slashed: {full_defaults.get('slashed')}")
    print(f"  effective_balance: {full_defaults.get('effective_balance')}")
    print(f"  committee_assignments (JIT): {full_defaults.get('committee_assignments')}")

    # Test validation functions
    print(f"\nValidation Functions:")
    print(f"  Valid Pubkey: {is_valid_pubkey('0x' + 'a' * 96)}")
    print(f"  Invalid Pubkey: {is_valid_pubkey('0x' + 'a' * 95)}")
    print(f"  Valid Withdrawal Credentials: {is_valid_withdrawal_credentials('0x' + 'b' * 64)}")
    print(f"  Invalid Withdrawal Credentials: {is_valid_withdrawal_credentials('0x' + 'b' * 63)}")
    print(f"  Valid Status (active_ongoing): {is_valid_validator_status('active_ongoing')}")
    print(f"  Invalid Status (non_existent): {is_valid_validator_status('non_existent')}")

    print("\n✅ Validator Configuration Test Complete!")