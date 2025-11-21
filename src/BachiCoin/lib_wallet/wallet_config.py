#!/usr/bin/env python3
"""
wallet_config.py

This module defines the master configuration, data schemas, and default values
for the BachiCoin wallet. It centralizes all static wallet-related constants
and settings, ensuring a single source of truth for wallet architecture.
"""

import re
from enum import Enum
from typing import Dict, List, Any

WALLET_INDEX_KEY = "wallet_index"

# --- Wallet Enums ---

class WalletType(Enum):
    """Categorizes wallets by their intended use case."""
    DEFAULT = "default"
    PRIVATE = "private"
    BUSINESS = "business"
    CHARITY = "charity"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    MINT = "mint"
    BURN = "burn"
    POOL = "pool"


class WalletSecurityType(Enum):
    """Defines the security level or type of the wallet."""
    HOT = "hot"
    COLD = "cold"
    HARDWARE = "hardware"
    MULTISIG = "multisig"


class WalletStatus(Enum):
    """Represents the operational status of a wallet."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"
    ARCHIVED = "archived"


class Network(Enum):
    """Specifies the blockchain network the wallet operates on."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    REGTEST = "regtest"


class Currency(Enum):
    """Defines the cryptocurrencies supported by the wallet."""
    BACHI = "BACHI"
    BTC = "BTC"
    ETH = "ETH"


class AccountType(Enum):
    """Distinguishes between different types of Ethereum accounts."""
    EOA = "eoa"
    CONTRACT = "contract"
    GENESIS = "genesis"
    MINT = "mint"
    BURN = "burn"


# --- Wallet Configuration Class ---

class WalletConfig:
    """
    A centralized configuration class for the wallet module.

    This class holds all master schemas, constants, constraints, and default
    values related to wallet structure and behavior. It is designed to be a
    static container of configuration data.
    """
    # Schema version for future migration purposes
    WALLET_SCHEMA_VERSION = 2 # Incremented due to ID format change

    # JIT (Just-In-Time) fields are populated during runtime, not from static defaults
    JIT_FIELDS = [
        "wallet_id",
        "addresses",
        "created_at",
        "last_modified",
    ]

    # --- Core Constants and Constraints ---
    WALLET_ID_PATTERN = re.compile(r'^W_[a-fA-F0-9]{16}$') # Updated for hash-based IDs
    ADDRESS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$'
)
    HASH_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$'
)

    MAX_NAME_LENGTH = 50
    MAX_WALLET_COUNT = 7
    PRECISION_DECIMALS = 8
    MIN_BALANCE = 0.0
    MAX_BALANCE = 1_000_000_000.0  # 1 billion

    # --- Default Values ---
    DEFAULT_CURRENCY = Currency.BACHI.value
    DEFAULT_NETWORK = Network.TESTNET.value
    DEFAULT_WALLET_TYPE = WalletType.DEFAULT.value
    DEFAULT_SECURITY_TYPE = WalletSecurityType.HOT.value
    DEFAULT_STATUS = WalletStatus.ACTIVE.value
    DEFAULT_ACCOUNT_TYPE = AccountType.EOA.value
    DEFAULT_BALANCE = 0.0
    DEFAULT_NONCE = 0

    # --- Master Schema Definition ---
    _WALLET_MASTER_SCHEMA: Dict[str, Dict[str, Any]] = {
        # Core Identification
        "wallet_id": {"type": str, "required": True, "immutable": True, "format": "wallet_id"},
        "user_id": {"type": str, "required": True, "immutable": True, "format": "user_id"},
        "name": {"type": str, "required": True, "format": "wallet_name", "default": "MyBachiWallet"},

        # Embedded ETH Account State
        "balance": {"type": (int, float), "required": True, "default": DEFAULT_BALANCE, "min_value": MIN_BALANCE},
        "nonce": {"type": int, "required": True, "default": DEFAULT_NONCE, "min_value": 0},
        "storage_root": {"type": str, "required": False, "format": "hash", "default": None},
        "code_hash": {"type": str, "required": False, "format": "hash", "default": None},

        # Wallet Classification
        "wallet_type": {"type": str, "required": True, "default": DEFAULT_WALLET_TYPE,
                        "allowed_values": [wt.value for wt in WalletType]},
        "security_type": {"type": str, "required": False, "default": DEFAULT_SECURITY_TYPE,
                          "allowed_values": [st.value for st in WalletSecurityType]},
        "status": {"type": str, "required": True, "default": DEFAULT_STATUS,
                   "allowed_values": [s.value for s in WalletStatus]},

        # Network and Currency
        "network": {"type": str, "required": True, "default": DEFAULT_NETWORK,
                    "allowed_values": [n.value for n in Network]},
        "currency": {"type": str, "required": True, "default": DEFAULT_CURRENCY,
                     "allowed_values": [c.value for c in Currency]},

        # Multi-address support (HD wallet structure)
        "addresses": {"type": dict, "required": True},

        # Cryptographic Material (No longer stored in the wallet record)
        "public_key": {"type": str, "required": False, "default": None},

        # Timestamps
        "created_at": {"type": str, "required": True, "format": "iso8601", "immutable": True},
        "last_modified": {"type": str, "required": True, "format": "iso8601"},
        "last_tx_at": {"type": str, "required": False, "format": "iso8601", "default": None},

        # Flexible Metadata
        "metadata": {"type": dict, "required": False, "default": {}},
    }

    # --- Schema Views for Different Operations ---
    WALLET_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "full_schema": list(_WALLET_MASTER_SCHEMA.keys()),
        "signing": ["wallet_id", "addresses"],
        "update": ["name", "wallet_type", "security_type", "status", "metadata"],
        "index": ["user_id", "name", "addresses", "balance", "nonce", "wallet_type", "status", "network", "currency",
                  "created_at", "last_modified"],
        "balance": ["wallet_id", "balance", "nonce", "last_tx_at"],
        "crypto": ["addresses"],
        "sensitive": [], # No sensitive fields stored anymore
        "system": ["name", "wallet_type", "balance", "nonce", "network", "currency", "metadata", "created_at",
                   "last_modified"],
    }

    # --- Defaults Based on Wallet Type ---
    WALLET_TYPE_DEFAULTS = {
        WalletType.DEFAULT.value: {"security_type": WalletSecurityType.HOT.value,
                                   "metadata": {"description": "Default wallet for general use"}},
        WalletType.PRIVATE.value: {"security_type": WalletSecurityType.COLD.value,
                                   "metadata": {"description": "Private wallet for personal funds",
                                                "privacy_level": "high"}},
        WalletType.BUSINESS.value: {"security_type": WalletSecurityType.HOT.value,
                                    "metadata": {"description": "Business wallet for commercial transactions",
                                                 "tax_reporting": True}},
        WalletType.CHARITY.value: {"security_type": WalletSecurityType.HOT.value,
                                   "metadata": {"description": "Charity wallet for donations",
                                                "public_donations": True}},
        WalletType.SAVINGS.value: {"security_type": WalletSecurityType.COLD.value,
                                   "metadata": {"description": "Long-term savings wallet"}},
        WalletType.INVESTMENT.value: {"security_type": WalletSecurityType.HARDWARE.value,
                                      "metadata": {"description": "Investment wallet for trading"}},
        WalletType.MINT.value: {"security_type": WalletSecurityType.HOT.value,
                                "metadata": {"description": "System mint wallet for token creation",
                                             "system_wallet": True}},
        WalletType.BURN.value: {"security_type": WalletSecurityType.HOT.value,
                                "metadata": {"description": "System burn wallet for token destruction",
                                             "system_wallet": True}},
        WalletType.POOL.value: {"security_type": WalletSecurityType.HOT.value,
                                "metadata": {"description": "System pool wallet for liquidity/bridge operations",
                                             "system_wallet": True}},
    }

    @classmethod
    def get_required_fields(cls, view: str = "full_schema") -> List[str]:
        """Returns the list of required fields for a given schema view."""
        schema = get_wallet_schema_view(view)
        return [field for field, config in schema.items() if config.get("required")]

    @classmethod
    def get_allowed_values(cls, field_name: str) -> List[Any]:
        """Returns the list of allowed values for a specific schema field."""
        return cls._WALLET_MASTER_SCHEMA.get(field_name, {}).get("allowed_values", [])

    @classmethod
    def get_field_constraints(cls, field_name: str) -> Dict[str, Any]:
        """Returns all defined constraints for a specific schema field."""
        return cls._WALLET_MASTER_SCHEMA.get(field_name, {})

    @classmethod
    def get_sensitive_fields(cls) -> List[str]:
        """Returns a list of fields marked as sensitive."""
        return [k for k, v in cls._WALLET_MASTER_SCHEMA.items() if v.get("sensitive")]

    @classmethod
    def get_immutable_fields(cls) -> List[str]:
        """Returns a list of fields that cannot be changed after creation."""
        return [k for k, v in cls._WALLET_MASTER_SCHEMA.items() if v.get("immutable")]


# --- Module-level Helper Functions ---

def get_wallet_schema_view(view: str) -> Dict[str, Any]:
    """
    Retrieves a specific subset (view) of the master wallet schema.

    Args:
        view: The name of the schema view to retrieve (e.g., "index", "update").

    Returns:
        A dictionary representing the requested subset of the schema.
    """
    assert view in WalletConfig.WALLET_SCHEMA_VIEWS, f"Unknown wallet schema view: {view}"
    view_fields = WalletConfig.WALLET_SCHEMA_VIEWS[view]
    return {k: WalletConfig._WALLET_MASTER_SCHEMA[k] for k in view_fields if k in WalletConfig._WALLET_MASTER_SCHEMA}


def get_wallet_full_defaults() -> Dict[str, Any]:
    """
    Constructs a dictionary with default values for a new wallet object.
    It intelligently handles static defaults, JIT fields, and empty values.

    Returns:
        A dictionary populated with the complete set of default values.
    """
    defaults = {}
    for field, config in WalletConfig._WALLET_MASTER_SCHEMA.items():
        if field in WalletConfig.JIT_FIELDS:
            defaults[field] = None  # JIT fields are populated at runtime
        elif "default" in config:
            defaults[field] = config["default"]
        else:
            # Assign an appropriate "empty" value for fields without a default
            field_type = config.get("type")
            if field_type == dict:
                defaults[field] = {}
            elif field_type == list:
                defaults[field] = []
            else:
                defaults[field] = None  # For str, (int, float), etc.
    return defaults


def get_wallet_defaults_for_view(view: str) -> Dict[str, Any]:
    """
    Gets the default values for all fields within a specific schema view.

    Args:
        view: The name of the schema view.

    Returns:
        A dictionary of fields and their default values for that view.
    """
    schema = get_wallet_schema_view(view)
    return {field: config.get("default") for field, config in schema.items() if "default" in config}


def is_jit_field(field_name: str) -> bool:
    """Checks if a field is a Just-In-Time (JIT) field."""
    return field_name in WalletConfig.JIT_FIELDS


if __name__ == "__main__":
    """
    A simple smoke test to ensure the configuration loads and functions correctly.
    """
    print("--- Running wallet_config.py Smoke Test ---")

    # 1. Test fetching full defaults
    defaults = get_wallet_full_defaults()
    assert isinstance(defaults, dict), "get_wallet_full_defaults should return a dict."
    assert defaults["balance"] == 0.0, "Default balance should be 0.0."
    assert defaults["wallet_id"] is None, "JIT field 'wallet_id' should be None by default."
    print("✅ get_wallet_full_defaults() seems OK.")

    # 2. Test fetching a schema view
    index_view = get_wallet_schema_view("index")
    assert isinstance(index_view, dict), "get_wallet_schema_view should return a dict."
    assert "user_id" in index_view, "'user_id' should be in the index view."
    assert "mnemonic" not in index_view, "Sensitive field 'mnemonic' should not be in the index view."
    print("✅ get_wallet_schema_view() seems OK.")

    # 3. Test WalletConfig class methods
    required = WalletConfig.get_required_fields()
    sensitive = WalletConfig.get_sensitive_fields()
    assert isinstance(required, list) and "wallet_id" in required, "get_required_fields failed."
    assert isinstance(sensitive, list) and not sensitive, "get_sensitive_fields should now be empty."
    print("✅ WalletConfig class methods seem OK.")

    # 4. Test JIT field checker
    assert is_jit_field("created_at") is True, "is_jit_field check failed for 'created_at'."
    assert is_jit_field("name") is False, "is_jit_field check failed for 'name'."
    print("✅ is_jit_field() seems OK.")

    print("\n--- Smoke Test Passed Successfully! ---")
