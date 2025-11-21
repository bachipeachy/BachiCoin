#!/usr/bin/env python3
"""Modern ETH transaction configuration - EIP-1559 Type 2 transactions only
CLEAN: No legacy support, proper separation from mempool concerns.
This module contains only static configuration data and utility functions that operate on it.
"""

import re
from enum import Enum
from typing import Dict, Any, List

from BachiCoin.lib_crossmodule.crossmodule_config import NetworkType, Currency

TX_INDEX_KEY = "tx_index"

TX_SCHEMA_VERSION: int = 1  # EIP-1559 Type 2 transactions only

# JIT (Just-In-Time) fields - populated during processing
JIT_FIELDS: List[str] = [
    "tx_hash",  # Generated during signing
    "nonce",  # Managed by account state
    "base_fee_per_gas",  # Set by protocol during execution
    "effective_gas_price",  # Calculated during execution
    "gas_used",  # Set after execution
    "total_fee",  # Calculated after execution
    "timestamp",  # Created at transaction time
    "created_at",  # Created at transaction time
    "last_modified",  # Updated on changes
    "block_number",  # Set when included in block
    "block_hash",  # Set when included in block
    "transaction_index",  # Set when included in block
    "confirmations",  # Dynamic based on current block
]


class TxType(Enum):
    """
    Core BachiCoin transaction types, designed for clarity and purpose.
    """
    # ---- Core Value Transfer ----
    TRANSFER = "transfer"        # P2P value transfer

    # ---- Monetary Supply Operations ----
    MINT = "mint"                # Create new supply
    BURN = "burn"                # Permanently remove from supply
    POOL = "pool"                # Moves mint funds to pool

    # ---- Staking (Proof-of-Stake) ----
    STAKE = "stake"              # Lock funds to become a validator
    UNSTAKE = "unstake"            # Release staked funds

    # ---- System-Generated Operations ----
    REWARD = "reward"            # Block or staking rewards
    SLASH = "slash"              # Penalty for validator misbehavior

    # ---- Future Use: Smart Contracts & Governance ----
    CONTRACT_CALL = "contract_call"
    CONTRACT_DEPLOY = "contract_deploy"
    GOVERNANCE = "governance"


class Priority(Enum):
    """EIP-1559 priority levels for fee estimation"""
    SLOW = "slow"  # Low priority fee
    STANDARD = "standard"  # Standard inclusion
    FAST = "fast"  # Fast inclusion
    URGENT = "urgent"  # Next block inclusion


class TxConfig:
    """Modern transaction configuration - EIP-1559 Type 2 only.
    This class contains only static configuration data.
    """

    # Validation patterns (current Ethereum standards)
    TX_HASH_PATTERN: re.Pattern = re.compile(r'^0x[a-fA-F0-9]{64}$')
    ADDRESS_PATTERN: re.Pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
    ETH_SIGNATURE_PATTERN: re.Pattern = re.compile(r'^0x[a-fA-F0-9]{130}$')  # ETH: 65 bytes hex
    BTC_SIGNATURE_PATTERN: re.Pattern = re.compile(r'^[A-Za-z0-9+/]+={0,2}$')  # Bitcoin: Base64 DER

    # Protocol constraints (EIP-1559)
    MAX_GAS_LIMIT: int = 30_000_000  # Current Ethereum block gas limit
    MAX_PRIORITY_FEE: float = 1000.0  # GWEI - reasonable upper bound
    MAX_BASE_FEE: float = 1000.0  # GWEI - for sanity checks
    MIN_GAS_LIMIT: int = 21_000  # Simple transfer minimum

    # Defaults
    DEFAULT_NETWORK: str = NetworkType.TESTNET.value
    DEFAULT_CURRENCY: str = Currency.BACHI.value
    DEFAULT_GAS_LIMIT: int = 21_000
    DEFAULT_CHAIN_ID: int = 1337  # BachiCoin testnet
    DEFAULT_TX_VERSION: int = 0

    # EIP-1559 fee defaults by priority (GWEI)
    FEE_DEFAULTS: Dict[str, Dict[str, float]] = {
        Priority.SLOW.value: {
            "max_fee_per_gas": 20.0,
            "max_priority_fee_per_gas": 1.0,
        },
        Priority.STANDARD.value: {
            "max_fee_per_gas": 40.0,
            "max_priority_fee_per_gas": 2.0,
        },
        Priority.FAST.value: {
            "max_fee_per_gas": 80.0,
            "max_priority_fee_per_gas": 5.0,
        },
        Priority.URGENT.value: {
            "max_fee_per_gas": 200.0,
            "max_priority_fee_per_gas": 10.0,
        }
    }

    # Gas estimates by transaction type
    GAS_ESTIMATES: Dict[str, int] = {
        TxType.TRANSFER.value: 21_000,
        TxType.MINT.value: 21_000,  # System-level, but assign gas for fee calculation
        TxType.BURN.value: 21_000,
        TxType.STAKE.value: 100_000,
        TxType.UNSTAKE.value: 80_000,
        TxType.REWARD.value: 0,  # Purely a state change, no gas
        TxType.SLASH.value: 0,   # Purely a state change, no gas
        TxType.CONTRACT_CALL.value: 150_000,
        TxType.CONTRACT_DEPLOY.value: 1_000_000,
    }

    # EIP-1559 Type 2 Transaction Schema
    _TX_SCHEMA: Dict[str, Dict[str, Any]] = {
        # Core identity
        "tx_hash": {"type": str, "required": False, "immutable": True, "format": "tx_hash"},
        "tx_type": {"type": str, "required": True, "default": TxType.TRANSFER.value, "immutable": True},
        "chain_id": {"type": int, "required": True, "default": DEFAULT_CHAIN_ID, "immutable": True},
        "tx_version": {"type": int, "required": True, "default": DEFAULT_TX_VERSION, "immutable": True},

        # Accounts and value
        "from_address": {"type": str, "required": False, "format": "address"}, 
        "to_address": {"type": str, "required": False, "format": "address"},   
        "amount": {"type": (int, float), "required": True, "default": 0.0, "min_value": 0},
        "currency": {"type": str, "required": True, "default": DEFAULT_CURRENCY},
        "network": {"type": str, "required": True, "default": DEFAULT_NETWORK},

        # Account state
        "nonce": {"type": int, "required": False, "min_value": 0}, 

        # EIP-1559 gas pricing
        "gas_limit": {"type": int, "required": True, "default": DEFAULT_GAS_LIMIT, "min_value": MIN_GAS_LIMIT},
        "max_fee_per_gas": {"type": (int, float), "required": True, "min_value": 0},
        "max_priority_fee_per_gas": {"type": (int, float), "required": True, "min_value": 0},

        # Execution results (JIT)
        "base_fee_per_gas": {"type": float, "required": False, "default": 0.0},
        "effective_gas_price": {"type": float, "required": False, "default": 0.0},
        "gas_used": {"type": int, "required": False, "default": 0},
        "total_fee": {"type": float, "required": False, "default": 0.0},

        # Smart contract fields
        "data": {"type": str, "required": False, "default": "0x"},
        "access_list": {"type": list, "required": False, "default": []},

        # Block inclusion (JIT)
        "block_number": {"type": int, "required": False, "default": None},
        "block_hash": {"type": str, "required": False, "format": "tx_hash", "default": None},
        "transaction_index": {"type": int, "required": False, "default": None},
        "confirmations": {"type": int, "required": False, "default": 0},

        # Cryptography
        "signature": {"type": str, "required": False, "format": "signature"},
        "recovery_id": {"type": int, "required": False, "default": 0},

        # Timestamps (JIT)
        "timestamp": {"type": str, "required": True, "format": "iso8601"},
        "created_at": {"type": str, "required": True, "format": "iso8601"},
        "last_modified": {"type": str, "required": False, "format": "iso8601"},
        "submitted_at": {"type": str, "required": False, "format": "iso8601"},
        "confirmed_at": {"type": str, "required": False, "format": "iso8601"},

        # Metadata
        "memo": {"type": str, "required": False, "default": ""},
        "metadata": {"type": dict, "required": False, "default": {}},
        "status": {"type": str, "required": False, "default": "pending"},
    }

    # Schema views for different use cases
    SCHEMA_VIEWS: Dict[str, List[str]] = {
        "full": list(_TX_SCHEMA.keys()),

        # Signing payload (EIP-1559 RLP encoding order)
        "signing": [
            "chain_id", "from_address", "tx_type", "nonce", "max_priority_fee_per_gas", "max_fee_per_gas",
            "gas_limit", "to_address", "amount", "data", "access_list"
        ],

        # Mempool submission
        "mempool": [
            "tx_hash", "from_address", "to_address", "amount", "nonce",
            "max_fee_per_gas", "max_priority_fee_per_gas", "gas_limit",
            "tx_type", "timestamp", "submitted_at", "signature"
        ],

        # Block inclusion
        "execution": [
            "tx_hash", "block_number", "block_hash", "transaction_index",
            "gas_used", "effective_gas_price", "total_fee", "base_fee_per_gas",
            "confirmed_at"
        ],

        # Storage/indexing
        "index": [
            "tx_hash", "tx_type", "from_address", "to_address", "amount", "currency",
            "block_number", "timestamp", "total_fee", "nonce", "confirmations",
            "network", "memo", "max_fee_per_gas", "max_priority_fee_per_gas", "status"
        ],

        # Canonical fields for tx_hash computation
        "canonical": [
            "access_list", "amount", "chain_id", "currency", "data",
            "from_address", "gas_limit", "max_fee_per_gas", "max_priority_fee_per_gas",
            "memo", "network", "nonce", "to_address", "tx_type", "tx_version"
        ]
    }

    @staticmethod
    def calculate_effective_gas_price(max_fee: float, max_priority: float, base_fee: float) -> float:
        """Calculate effective gas price per EIP-1559."""
        return min(max_priority, max_fee - base_fee) + base_fee

    @staticmethod
    def calculate_total_fee(gas_used: int, effective_gas_price: float) -> float:
        """Calculate total transaction fee."""
        return round(gas_used * effective_gas_price / 1e9, 8)  # Convert from GWEI to BACHI

# Global constant for decimal precision
DECIMAL_PLACES = 8

def get_tx_schema_view(view: str) -> Dict[str, Any]:
    """Get schema fields for specific view"""
    assert view in TxConfig.SCHEMA_VIEWS, f"Unknown schema view: {view}"
    return {k: TxConfig._TX_SCHEMA[k] for k in TxConfig.SCHEMA_VIEWS[view]}

def get_tx_defaults() -> Dict[str, Any]:
    """Get default values for transaction fields based on TxConfig's schema."""
    defaults = {}
    for field, config in TxConfig._TX_SCHEMA.items():
        if field in JIT_FIELDS:
            defaults[field] = None
        elif "default" in config:
            defaults[field] = config["default"]
        else:
            # Type-based defaults
            field_type = config.get("type", str)
            if field_type == str:
                defaults[field] = ""
            elif field_type in (int, float):
                defaults[field] = 0
            elif field_type == dict:
                defaults[field] = {}
            elif field_type == list:
                defaults[field] = []
            else:
                defaults[field] = None
    return defaults


if __name__ == '__main__':
    print("--- Smoke Test for tx_config.py ---")
    print(f"Default Network: {TxConfig.DEFAULT_NETWORK}")
    print(f"Default Gas Limit: {TxConfig.DEFAULT_GAS_LIMIT}")
    print(f"Default Tx Version: {TxConfig.DEFAULT_TX_VERSION}")
    print(f"Signing Schema Fields: {TxConfig.SCHEMA_VIEWS['signing']}")
    print(f"Canonical Schema Fields: {TxConfig.SCHEMA_VIEWS['canonical']}")
    print(f"TxType Enum values: {[e.value for e in TxType]}")
    print(f"JIT Fields: {JIT_FIELDS}")
    print("---" * 10)
    print("Testing get_tx_defaults...")
    defaults = get_tx_defaults()
    assert isinstance(defaults, dict)
    assert "tx_hash" in defaults
    assert defaults["tx_hash"] is None
    assert defaults["amount"] == 0.0
    assert defaults["tx_version"] == 0
    print("get_tx_defaults passed.")
    print("Testing calculate_effective_gas_price...")
    effective_price = TxConfig.calculate_effective_gas_price(100.0, 10.0, 50.0)
    assert effective_price == 60.0
    print("calculate_effective_gas_price passed.")
    print("Testing calculate_total_fee...")
    total_fee = TxConfig.calculate_total_fee(21000, 60.0)
    assert total_fee == 0.00126
    print("calculate_total_fee passed.")
    print("--- Smoke Test Passed ---")
