#!/usr/bin/env python3
"""wallet_helper.py -- contains the pure business logic and helper functions for wallet management"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from BachiCoin.lib_wallet.wallet_config import get_wallet_schema_view
from BachiCoin.lib_wallet.wallet_validation import WalletValidation, _format_balance
from BachiCoin.lib_crossmodule.id_generator import generate_hash_id

# =================== WALLET CREATION ===================

def prepare_wallet_data(user_id: str, wallet_data: Dict[str, Any],
                        addresses: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepares full wallet data by applying defaults and embedding the provided addresses.
    This function is now deterministic and does not handle private keys.
    """

    # 1. Copy defaults + caller data
    full_data = {
        "user_id": user_id,
        "name": wallet_data.get("name", "Unnamed Wallet"),
        "wallet_type": wallet_data.get("wallet_type", "default"),
        "security_type": wallet_data.get("security_type", "hot"),
        "status": "active",
        "network": wallet_data.get("network", "testnet"),
        "currency": wallet_data.get("currency", "BACHI"),
        "balance": 0.0,
        "nonce": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_modified": datetime.now(timezone.utc).isoformat(),
        "metadata": wallet_data.get("metadata", {}),
    }

    # Generate deterministic wallet_id based on user_id and wallet_type
    # The wallet_id should be generated before adding to full_data to ensure it's part of the data used for hashing if needed
    # However, for determinism, we use the core identifying properties.
    # For wallets, user_id and wallet_type are key for deterministic ID within a user's context.
    id_data = {
        "user_id": user_id,
        "wallet_type": full_data["wallet_type"],
        "name": full_data["name"] # Include name for more uniqueness if user has multiple wallets of same type
    }
    full_data["wallet_id"] = generate_hash_id("W", id_data)

    # 2. Embed the provided addresses dictionary directly
    full_data["addresses"] = addresses
    # Top-level convenience copy of the primary EOA public key
    full_data["public_key"] = addresses.get("eoa", {}).get("public_key")

    return full_data

def create_index_entry(wallet_data: Dict[str, Any], storage) -> bool:
    """Creates a new entry in the wallet index from wallet data."""
    index_fields = get_wallet_schema_view("index").keys()
    entry = {field: wallet_data.get(field) for field in index_fields}

    entry["address_count"] = len(wallet_data.get("addresses", {}))
    entry["available_address_types"] = list(wallet_data.get("addresses", {}).keys())

    def add_func(index_data):
        index_data.setdefault("wallets", {})[wallet_data["wallet_id"]] = entry
        return index_data

    return storage.update_index_data(add_func) is not None

def update_index_entry(wallet_id: str, changes: Dict[str, Any], storage) -> bool:
    """Updates specific fields for a wallet in the index."""

    def update_func(index_data):
        if "wallets" in index_data and wallet_id in index_data["wallets"]:
            index_data["wallets"][wallet_id].update(changes)
        return index_data

    return storage.update_index_data(update_func) is not None

def remove_index_entry(wallet_id: str, storage) -> bool:
    """Removes a wallet from the index."""

    def remove_func(index_data):
        index_data.get("wallets", {}).pop(wallet_id, None)
        return index_data

    return storage.update_index_data(remove_func) is not None

def validate_wallet_before_creation(full_wallet_data: Dict[str, Any]):
    """Validates a wallet object before saving."""
    errors = WalletValidation.validate_wallet_data(full_wallet_data, context="create")
    if errors:
        raise ValueError(f"Wallet creation validation failed: {errors}")

def update_wallet_state(storage, wallet_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates wallet record and index entry."""
    def update_func(wallet_data):
        wallet_data.update(update_data)
        wallet_data["last_modified"] = datetime.now(timezone.utc).isoformat()
        return wallet_data

    updated_wallet = storage.update_wallet(wallet_id, update_func)
    if not updated_wallet:
        return False

    # Filter for fields that are part of the index schema
    index_schema_fields = get_wallet_schema_view("index").keys()
    index_changes = {k: v for k, v in update_data.items() if k in index_schema_fields}

    # If any indexed fields were changed, update the index
    if index_changes:
        # Also propagate the last_modified timestamp to the index
        index_changes["last_modified"] = updated_wallet["last_modified"]
        return update_index_entry(wallet_id, index_changes, storage)

    return True

def adjust_wallet_balance(service, wallet_id: str, amount_delta: float) -> bool:
    """Update wallet balance by adding amount_delta - fixes index sync"""
    # Get current balance from wallet record
    wallet_data = service.get_wallet(wallet_id)
    assert wallet_data, f"Wallet {wallet_id} not found"

    current_balance = wallet_data.get("balance", 0.0)
    new_balance = _format_balance(current_balance + amount_delta)

    # Update both storage and index atomically
    return service.update_account_state(wallet_id, balance=new_balance)

def update_account_state(storage, wallet_id: str, balance: Optional[float] = None, nonce: Optional[int] = None) -> bool:
    """Updates balance/nonce state."""
    update_data = {}
    if balance is not None:
        update_data["balance"] = _format_balance(balance)
    if nonce is not None:
        update_data["nonce"] = nonce

    if not update_data:
        return True

    return update_wallet_state(storage, wallet_id, update_data)
