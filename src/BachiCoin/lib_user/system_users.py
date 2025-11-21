#!/usr/bin/env python3
"""system_users.py - A utility script to create foundational system users."""

from typing import Dict
from BachiCoin.lib_user.user_config import UserType
from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_user.user_service_factory import UserServiceFactory


def _create_or_find_user(user_service: UserIndexService, first_name: str, last_name: str, email: str, bio: str, user_type_enum: UserType) -> str:
    """Helper to create a system user or find it if it already exists."""
    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email_registration": email,
        "user_type": user_type_enum.value,
        "kyc_verified": True,
        "bio": bio
    }
    result = user_service.create_user_with_index(payload)
    if result and result.get("user_id"):
        print(f"✅ Created system user: {first_name} {last_name}")
        return result["user_id"]
    
    print(f"User '{first_name} {last_name}' may already exist. Attempting to find by email...")
    users = user_service.search_users(email)
    if users:
        return users[0]["user_id"]
    raise RuntimeError(f"Failed to create or find the {first_name} {last_name} user.")

def create_system_users(user_service: UserIndexService) -> Dict[str, str]:
    """Creates the two foundational system users: ledger system and Genesis User."""
    print("--- Bootstrapping Foundational System Users ---")
    
    ledger_system_id = _create_or_find_user(
        user_service,
        "Ledger",
        "System",
        "ledger.system@bachicoin.org",
        "System account for mint, burn, and pool operations.",
        UserType.LEDGER
    )
    
    genesis_user_id = _create_or_find_user(
        user_service,
        "Genesis",
        "User",
        "genesis.user@bachicoin.org",
        "System account for initial network funding.",
        UserType.GENESIS
    )

    return {
        "ledger_system": ledger_system_id,
        "genesis_user": genesis_user_id
    }

if __name__ == "__main__":
    from tests.test_config import dirs

    print("--- Running System Users Bootstrap Standalone ---")
    # Directly instantiate UserIndexService using UserServiceFactory
    service = UserServiceFactory.create_user_index_service(dirs)
    system_user_ids = create_system_users(service)
    print(f"\n✅ Bootstrap complete. System User IDs: {system_user_ids}")
    
    # Verification
    ledger_summary = service.get_user_summary(system_user_ids["ledger_system"])
    assert ledger_summary, "Could not retrieve Ledger System summary."
    print(f"✅ Verification successful. Found user: {ledger_summary.get('first_name')} {ledger_summary.get('last_name')}")
    
    genesis_summary = service.get_user_summary(system_user_ids["genesis_user"])
    assert genesis_summary, "Could not retrieve Genesis User summary."
    print(f"✅ Verification successful. Found user: {genesis_summary.get('first_name')} {genesis_summary.get('last_name')}")
