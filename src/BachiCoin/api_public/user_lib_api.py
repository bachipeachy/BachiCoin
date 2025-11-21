#!/usr/bin/env python3
"""user_lib_api.py - public API layer for the User Module."""

from typing import Dict, Any, List, Optional

# Import services and factories
from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg
from BachiCoin.lib_user.system_users import create_system_users as _create_system_users
from BachiCoin.lib_user.user_config import UserType as _UserType

UserType = _UserType

def create_user_index_service(*args, **kwargs) -> UserIndexService:
    """
    Creates UserIndexService by delegating to the UserServiceFactory.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(UserServiceFactory.create_user_index_service, *args, **kwargs)

# =================== CORE API FUNCTIONS ===================

def create_user_with_index(
        user_service: UserIndexService,
        user_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Creates a new user, returning the user_id."""
    return user_service.create_user_with_index(user_data)

def delete_user_with_index(service: UserIndexService, user_id: str) -> bool:
    """Deletes a user record and their index entry."""
    return service.delete_user_with_index(user_id)

def list_users(service: UserIndexService) -> List[Dict[str, Any]]:
    """Lists summary data for all users."""
    return service.list_users()

def get_user_summary(service: UserIndexService, user_id: str) -> Optional[Dict[str, Any]]:
    """Gets a user's summary data (from the index for speed)."""
    return service.get_user_summary(user_id)

def get_user(service: UserIndexService, user_id: str) -> Optional[Dict[str, Any]]:
    """Gets a user's full data record."""
    return service.get_user(user_id)

# =================== STATE UPDATE API ===================

def update_user(service: UserIndexService, user_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates a user's general data fields."""
    return service.update_user(user_id, update_data)

def update_user_balance(service: UserIndexService, user_id: str, new_balance: float) -> bool:
    """Updates a user's total balance."""
    return service.update_user_balance(user_id, new_balance)

def add_wallet_to_user(service: UserIndexService, user_id: str, wallet_id: str) -> bool:
    """Adds a wallet ID to a user's list of wallets."""
    return service.add_wallet_to_user(user_id, wallet_id)

def remove_wallet_from_user(service: UserIndexService, user_id: str, wallet_id: str) -> bool:
    """Removes a wallet ID from a user's list of wallets."""
    return service.remove_wallet_from_user(user_id, wallet_id)

# =================== SEARCH & ANALYTICS API ===================

def search_users(service: UserIndexService, query: str) -> List[Dict[str, Any]]:
    """Searches for users by a query string."""
    return service.search_users(query)


def get_user_stats(service: UserIndexService) -> Dict[str, Any]:
    """Gets statistics about all users in the index."""
    return service.get_user_stats()

# =================== MAINTENANCE API ===================

def rebuild_user_index(service: UserIndexService) -> Dict[str, Any]:
    """Rebuilds the user index from the source data files."""
    return service.rebuild_index_from_records()

# =================== ORCHESTRATION API FUNCTIONS ===================

def create_system_users(user_service: UserIndexService) -> Dict[str, str]:
    """High-level wrapper to run the system user bootstrap process."""
    return _create_system_users(user_service)

# =================== SMOKE TEST ===================

if __name__ == "__main__":
    """A simple smoke test for the public User API."""
    from tests.test_config import dirs

    print("--- Running User API Smoke Test ---")
    user_service = create_user_index_service(dirs)
    print(f"✅ {user_service} with storage at {dirs.user}")

    user_payload = {
        "first_name": "Api",
        "last_name": "Test",
        "email_registration": "api.test@example.com",
    }
    creation_result = create_user_with_index(user_service, user_payload)
    assert creation_result and creation_result.get("user_id"), "User creation via API failed."
    user_id = creation_result["user_id"]
    print(f"✅ Orchestrated user creation successful. User ID: {user_id}")

    stats = get_user_stats(user_service)
    print(f"✅ user stats -> {stats}")

    search_results = search_users(user_service, "Api")
    print(f"✅ search_users -> {search_results}.")

    update_success = update_user(user_service, user_id, {"first_name": "ApiUpdated"})
    assert update_success, "update_user failed."
    updated_user = get_user_summary(user_service, user_id)
    assert updated_user["first_name"] == "ApiUpdated", "User name was not updated."
    print("✅ update_user successful.")

    print("\n--- Smoke Test Passed Successfully! ---")
