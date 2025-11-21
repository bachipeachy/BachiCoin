#!/usr/bin/env python3
"""user_config.py defines the configuration, constants, and master schema for the User module"""

import re
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List

from BachiCoin.lib_crossmodule.crossmodule_config import Currency

USER_INDEX_KEY = "user_index"

USER_SCHEMA_VERSION = 1 # Incremented version due to schema change

# JIT (Just-In-Time) fields - populated during processing, not in static defaults
JIT_FIELDS = [
    "user_id",
    "kyc_key",
    "created_at",
    "last_modified",
]


# --- Enums for Controlled Vocabularies ---

class UserType(Enum):
    """Defines user roles for PoS consensus and economic differentiation."""
    LEDGER = "ledger"
    GENESIS = "genesis"
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ORGANIZATION = "organization"
    VALIDATOR = "validator"
    DELEGATOR = "delegator"
    INSTITUTIONAL = "institutional"
    DEVELOPER = "developer"
    TESTNET = "testnet"


class UserStatus(Enum):
    """Defines the lifecycle status of a user account."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    VERIFIED = "verified"
    DELETED = "deleted"
    ARCHIVED = "archived"


class UserConfig:
    """
    A pure configuration class defining the user schema, constraints, and defaults.
    All schema-related logic is encapsulated here as class methods.
    """

    # --- Constants and Business Rules ---
    USER_ID_PATTERN = re.compile(r'^U_[a-f0-9]+$') # Updated for deterministic IDs
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')

    MAX_NAME_LENGTH = 50
    MAX_EMAIL_LENGTH = 100
    MAX_PHONE_LENGTH = 20
    MAX_COUNTRY_LENGTH = 50
    MAX_BIO_LENGTH = 500
    MAX_NOTES_LENGTH = 1000

    MAX_WALLET_COUNT = 7
    TESTNET_MAX_WALLET_COUNT = 10
    MIN_STAKE_AMOUNT = 1000.0
    TESTNET_MIN_STAKE = 100.0
    MAX_DELEGATION_FEE = 0.1

    DEFAULT_USER_TYPE = UserType.TESTNET.value
    DEFAULT_STATUS = UserStatus.ACTIVE.value
    DEFAULT_LANGUAGE = "en"
    DEFAULT_CURRENCY = Currency.BACHI.value

    SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "zh", "ja", "ko"]
    SUPPORTED_CURRENCIES = ["BTC", "USD", "EUR", "GBP", "JPY", "CNY", "BACHI"]
    BUSINESS_TYPES = ["corporation", "llc", "partnership", "sole_proprietorship",
                      "non_profit", "government", "educational", "other"]

    # --- Master Schema Definition ---
    _USER_MASTER_SCHEMA: Dict[str, Dict[str, Any]] = {
        # Core identification
        "user_id": {"type": str, "required": True, "immutable": True, "format": "user_id"},
        "first_name": {"type": str, "required": True, "min_length": 1, "max_length": MAX_NAME_LENGTH},
        "last_name": {"type": str, "required": True, "min_length": 1, "max_length": MAX_NAME_LENGTH},
        "email_registration": {"type": str, "required": True, "immutable": True, "format": "email"},
        "email_current": {"type": str, "required": True, "format": "email"},
        "kyc_key": {"type": str, "required": True, "immutable": True},

        # User classification
        "user_type": {"type": str, "required": True, "default": DEFAULT_USER_TYPE,
                      "allowed_values": [t.value for t in UserType]},
        "status": {"type": str, "required": True, "default": DEFAULT_STATUS,
                   "allowed_values": [s.value for s in UserStatus]},

        # Wallet associations (managed by wallet service)
        "wallet_ids": {"type": list, "required": False, "default": [], "computed": True},
        "total_balance": {"type": float, "required": False, "default": 0.0, "computed": True},

        # Timestamps
        "created_at": {"type": str, "required": True, "format": "iso8601", "immutable": True},
        "last_modified": {"type": str, "required": True, "format": "iso8601"},
        "last_active": {"type": float, "required": False},
        "last_login": {"type": float, "required": False},

        # Contact information
        "phone": {"type": str, "required": False, "max_length": MAX_PHONE_LENGTH, "format": "phone"},
        "country": {"type": str, "required": False, "max_length": MAX_COUNTRY_LENGTH},
        "address": {"type": str, "required": False, "max_length": 200},
        "city": {"type": str, "required": False, "max_length": MAX_COUNTRY_LENGTH},
        "postal_code": {"type": str, "required": False, "max_length": 20},

        # Profile
        "bio": {"type": str, "required": False, "max_length": MAX_BIO_LENGTH},
        "website": {"type": str, "required": False, "max_length": 200},
        "social_links": {"type": dict, "required": False, "default": {}},

        # Verification
        "email_verified": {"type": bool, "required": False, "default": False},
        "phone_verified": {"type": bool, "required": False, "default": False},
        "kyc_verified": {"type": bool, "required": False, "default": True},
        "two_factor_enabled": {"type": bool, "required": False, "default": False},

        # Business/Organization
        "organization_name": {"type": str, "required": False, "max_length": 100},
        "tax_id": {"type": str, "required": False, "max_length": 50},
        "business_type": {"type": str, "required": False, "allowed_values": BUSINESS_TYPES},

        # Preferences
        "language": {"type": str, "required": False, "default": DEFAULT_LANGUAGE,
                     "allowed_values": SUPPORTED_LANGUAGES},
        "timezone": {"type": str, "required": False},
        "currency_preference": {"type": str, "required": False, "default": DEFAULT_CURRENCY,
                                "allowed_values": SUPPORTED_CURRENCIES},
        "notification_preferences": {"type": dict, "required": False, "default": {}},

        # PoS Validator fields
        "validator_address": {"type": str, "required": False, "format": "eth_address"},
        "stake_amount": {"type": float, "required": False, "min_value": 0.0},
        "delegation_fee": {"type": float, "required": False, "min_value": 0.0, "max_value": MAX_DELEGATION_FEE},
        "validator_status": {"type": str, "required": False, "allowed_values": ["active", "inactive", "jailed"]},

        # System metadata
        "metadata": {"type": dict, "required": False, "default": {}},
        "tags": {"type": list, "required": False, "default": []},
        "notes": {"type": str, "required": False, "max_length": MAX_NOTES_LENGTH}
    }

    # --- Schema Views ---
    USER_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "full_schema": list(_USER_MASTER_SCHEMA.keys()),
        "create": [
            "first_name", "last_name", "email_registration", "user_type",
            "language", "currency_preference", "kyc_verified", "created_at", "last_modified"
        ],
        "update": [
            "first_name", "last_name", "email_current", "phone", "country", "address",
            "bio", "language", "currency_preference", "notification_preferences"
        ],
        "index": [
            "user_id", "first_name", "last_name", "email_current", "email_registration",
            "user_type", "status", "kyc_verified", "total_balance", "wallet_ids",
            "created_at", "kyc_key"
        ],
        "profile": [
            "user_id", "first_name", "last_name", "email_current", "phone", "country",
            "bio", "website", "language", "currency_preference", "wallet_ids", "total_balance"
        ],
        "auth": [
            "user_id", "email_current", "status", "email_verified", "kyc_verified",
            "two_factor_enabled", "last_login"
        ],
        "validator": [
            "user_id", "user_type", "validator_address", "stake_amount", "delegation_fee",
            "validator_status", "kyc_verified"
        ],
        "sensitive": ["user_id", "wallet_ids"]
    }

    # --- User Type Defaults ---
    USER_TYPE_DEFAULTS = {
        UserType.TESTNET.value: {
            "kyc_verified": True,
            "max_wallets": TESTNET_MAX_WALLET_COUNT,
            "min_stake": TESTNET_MIN_STAKE
        },
        UserType.INDIVIDUAL.value: {
            "kyc_verified": False,
            "max_wallets": MAX_WALLET_COUNT,
            "min_stake": MIN_STAKE_AMOUNT
        },
        UserType.VALIDATOR.value: {
            "kyc_verified": True,
            "max_wallets": MAX_WALLET_COUNT,
            "min_stake": MIN_STAKE_AMOUNT,
            "requires_stake": True
        }
    }

    # --- Encapsulated Class Methods for Schema Access ---

    @classmethod
    def get_user_schema_view(cls, view: str) -> Dict[str, Any]:
        """Gets the schema definition for a specific view."""
        assert view in cls.USER_SCHEMA_VIEWS, f"Unknown user schema view: {view}"
        view_fields = cls.USER_SCHEMA_VIEWS[view]
        return {k: cls._USER_MASTER_SCHEMA[k] for k in view_fields if k in cls._USER_MASTER_SCHEMA}

    @classmethod
    def get_user_defaults_for_view(cls, view: str) -> Dict[str, Any]:
        """Gets default values for all fields in a specific view."""
        schema = cls.get_user_schema_view(view)
        return {field: config.get("default") for field, config in schema.items() if "default" in config}

    @classmethod
    def get_user_full_defaults(cls) -> Dict[str, Any]:
        """Gets a complete default user object based on the master schema."""
        defaults = {}
        for field, config in cls._USER_MASTER_SCHEMA.items():
            if field in JIT_FIELDS:
                defaults[field] = None  # JIT fields are populated at runtime
            elif "default" in config:
                defaults[field] = config["default"]
            else:
                # Assign an appropriate empty value for fields without a default
                field_type = config.get("type", str)
                if field_type == list:
                    defaults[field] = []
                elif field_type == dict:
                    defaults[field] = {}
                else:
                    defaults[field] = None  # Default for str, int, float, bool
        return defaults

    @classmethod
    def get_required_fields(cls, view: str = "full_schema") -> List[str]:
        """Gets a list of all required fields for a given schema view."""
        schema = cls.get_user_schema_view(view)
        return [field for field, config in schema.items() if config.get("required", False)]

    @classmethod
    def get_sensitive_fields(cls) -> List[str]:
        """Gets a list of fields marked as sensitive."""
        return [k for k, v in cls._USER_MASTER_SCHEMA.items() if v.get("sensitive")]

    @classmethod
    def get_immutable_fields(cls) -> List[str]:
        """Gets a list of fields that cannot be changed after creation."""
        return [k for k, v in cls._USER_MASTER_SCHEMA.items() if v.get("immutable")]

    @classmethod
    def get_field_constraints(cls, field_name: str) -> Dict[str, Any]:
        """Gets the full constraint dictionary for a single field."""
        return cls._USER_MASTER_SCHEMA.get(field_name, {})

    @classmethod
    def get_user_type_defaults(cls, user_type: str) -> Dict[str, Any]:
        """Gets the default business rule values for a specific user type."""
        return cls.USER_TYPE_DEFAULTS.get(user_type, {})


# --- Module-level Utility Functions (Pure Functions) ---

def is_valid_user_id(user_id: str) -> bool:
    """Validate user ID format"""
    return bool(UserConfig.USER_ID_PATTERN.match(user_id))

def is_valid_email(email: str) -> bool:
    """Validate email format"""
    return bool(UserConfig.EMAIL_PATTERN.match(email))


def is_valid_phone(phone: str) -> bool:
    """Validate phone format"""
    return bool(UserConfig.PHONE_PATTERN.match(phone))


def is_valid_user_type(user_type: str) -> bool:
    """Validate user type"""
    return user_type in [t.value for t in UserType]


def is_valid_user_status(status: str) -> bool:
    """Validate user status"""
    return status in [s.value for s in UserStatus]


def is_valid_language(language: str) -> bool:
    """Validate language"""
    return language in UserConfig.SUPPORTED_LANGUAGES


def is_valid_currency(currency: str) -> bool:
    """Validate currency"""
    return currency in UserConfig.SUPPORTED_CURRENCIES


def is_testnet_user(user_type: str) -> bool:
    """Check if user is testnet user"""
    return user_type == UserType.TESTNET.value


def get_max_wallets(user_type: str) -> int:
    """Get maximum wallet count for user type"""
    if is_testnet_user(user_type):
        return UserConfig.TESTNET_MAX_WALLET_COUNT
    return UserConfig.MAX_WALLET_COUNT


def get_min_stake(user_type: str) -> float:
    """Get minimum stake amount for user type"""
    if is_testnet_user(user_type):
        return UserConfig.TESTNET_MIN_STAKE
    return UserConfig.MIN_STAKE_AMOUNT


def is_jit_field(field_name: str) -> bool:
    """Check if field is JIT (Just-In-Time) populated"""
    return field_name in JIT_FIELDS


def get_jit_fields() -> List[str]:
    """Get list of JIT fields"""
    return JIT_FIELDS.copy()


if __name__ == "__main__":
    """
    A simple smoke test to verify that the configuration can be loaded
    and accessed without errors. This is not a functional test.
    """
    print("--- Running UserConfig Smoke Test ---")

    try:
        # 1. Access a simple constant
        default_type = UserConfig.DEFAULT_USER_TYPE
        print(f"✅ Default User Type: {default_type}")

        # 2. Access an enum
        print(f"✅ UserType Enum 'VALIDATOR': {UserType.VALIDATOR.value}")

        # 3. Access a schema view
        create_view_fields = UserConfig.get_user_schema_view("create").keys()
        print(f"✅ 'create' view fields: {list(create_view_fields)}")

        # 4. Access field constraints
        email_constraints = UserConfig.get_field_constraints("email_registration")
        print(f"✅ Constraints for 'email_registration': {email_constraints}")

        # 5. Access user type defaults
        validator_defaults = UserConfig.get_user_type_defaults(UserType.VALIDATOR.value)
        print(f"✅ Defaults for a Validator: {validator_defaults}")

        # 6. Call a module-level utility function
        is_valid = is_valid_email("test@example.com")
        print(f"✅ Utility function 'is_valid_email' works: {is_valid}")

        print("\n--- UserConfig Smoke Test Passed Successfully! ---")

    except Exception as e:
        print(f"\n--- ❌ UserConfig Smoke Test FAILED! ❌ ---")
        print(f"Error: {e}")
        # Re-raise the exception to get a non-zero exit code
        raise
