#!/usr/bin/env python3
"""user_helper.py - Pure functions for user index and analytics."""

from typing import Dict, Any, List
from BachiCoin.lib_user.user_config import UserConfig
from BachiCoin.lib_user.user_validation import assert_valid_user_data

# =================== INDEX ENTRY HELPERS ===================

def create_index_entry(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Builds an index entry from a user record (pure, deterministic)."""
    assert_valid_user_data(user_data, "index")
    index_fields = UserConfig.get_user_schema_view("index").keys()
    return {field: user_data.get(field) for field in index_fields if field != "user_id"}

def update_index_entry(current_entry: Dict[str, Any], changes: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a new index entry with applied changes."""
    updated = current_entry.copy()
    updated.update(changes)
    return updated

def remove_index_entry(index_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Removes a user entry from index data."""
    if "users" in index_data:
        index_data["users"].pop(user_id, None)
    return index_data

# =================== STATISTICS HELPERS ===================

def calculate_user_index_stats(users: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate user statistics from index."""
    stats = {
        "total_users": len(users),
        "by_type": {},
        "by_status": {},
        "total_balance": 0.0,
        "total_wallets": 0
    }

    for user_info in users.values():
        user_type = user_info.get("user_type", "unknown")
        stats["by_type"][user_type] = stats["by_type"].get(user_type, 0) + 1

        status = user_info.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        # Safely handle None for total_balance before converting to float
        balance = user_info.get("total_balance")
        stats["total_balance"] += float(balance or 0.0)
        
        # Safely handle None for wallet_ids before calling len()
        wallet_ids = user_info.get("wallet_ids")
        stats["total_wallets"] += len(wallet_ids or [])

    return stats

# =================== REBUILD HELPERS ===================

def rebuild_index_from_records(all_user_ids: List[str], storage) -> Dict[str, Any]:
    """
    Rebuilds the user index from the storage layer.
    Pure in terms of logic — requires storage injection.
    """
    rebuilt_index = {"users": {}}
    processed = 0
    errors = 0

    for user_id in all_user_ids:
        user_data = storage.load_user(user_id)
        if user_data:
            index_fields = UserConfig.get_user_schema_view("index").keys()
            entry = {field: user_data.get(field) for field in index_fields if field != "user_id"}
            rebuilt_index["users"][user_id] = entry
            processed += 1
        else:
            errors += 1

    success = storage.save_index_data(rebuilt_index)
    return {
        "success": success,
        "processed": processed,
        "errors": errors,
        "total_users_scanned": len(all_user_ids),
    }