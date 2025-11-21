#!/usr/bin/env python3
"""user_storage_adapter.py - Provides a backend-agnostic storage adapter for data"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_user.user_config import USER_INDEX_KEY, UserConfig

class UserStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== CORE USER I/O OPERATIONS ===================

    def save_user(self, user_id: str, user_data: Dict[str, Any]) -> bool:
        """Saves a complete user data object."""
        return self.provider.save(user_id, user_data)

    def load_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Loads a complete user data object by its ID."""
        return self.provider.load(user_id)

    def update_user(self, user_id: str, update_func: Callable[[Dict], Dict]) -> Optional[Dict[str, Any]]:
        """Atomically updates a user record using a functional pattern."""
        current_data = self.load_user(user_id)
        if current_data is None:
            return None  # User does not exist

        # Apply the update logic from the provided function
        updated_data = update_func(current_data)

        # Automatically set the last_modified timestamp on every update
        updated_data["last_modified"] = datetime.now(timezone.utc).isoformat()

        if self.save_user(user_id, updated_data):
            return updated_data
        return None

    def delete_user_with_index(self, user_id: str) -> bool:
        """Deletes a user record by its ID."""
        return self.provider.delete(user_id)

    def user_exists(self, user_id: str) -> bool:
        """Checks if a user record exists."""
        return self.provider.exists(user_id)

    def list_users(self) -> List[str]:
        """Lists all user IDs in the storage."""
        return [key for key in self.provider.list_keys() if key != USER_INDEX_KEY]

    # =================== INDEX I/O OPERATIONS ===================

    def save_index_data(self, index_data: Dict[str, Any]) -> bool:
        """Saves the entire user index object."""
        return self.provider.save(USER_INDEX_KEY, index_data)

    def load_index_data(self) -> Optional[Dict[str, Any]]:
        """Loads the entire user index object."""
        return self.provider.load(USER_INDEX_KEY)

    def update_index_data(self, update_func: Callable[[Dict], Dict]) -> Optional[Dict[str, Any]]:
        """Atomically updates the user index using a functional pattern."""
        return self.provider.update(USER_INDEX_KEY, update_func)

    # =================== DERIVED QUERY OPERATIONS (INDEX-BASED) ===================

    def find_user_by_email(self, email: str) -> Optional[str]:
        """Finds a user ID by any of their email addresses from the index."""
        index_data = self.load_index_data()
        if not index_data or "users" not in index_data:
            return None

        email_lower = email.lower()
        for user_id, user_info in index_data["users"].items():
            # Ensure email values are treated as strings before calling .lower()
            email_current = str(user_info.get("email_current") or "").lower()
            email_system = str(user_info.get("email_system") or "").lower()

            if email_current == email_lower or email_system == email_lower:
                return user_id
        return None

    def find_user_by_kyc_key(self, kyc_key: str) -> Optional[str]:
        """Finds a user ID by their unique KYC key from the index."""
        index_data = self.load_index_data()
        if not index_data or "users" not in index_data:
            return None

        for user_id, user_info in index_data["users"].items():
            if user_info.get("kyc_key") == kyc_key:
                return user_id
        return None

    def load_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Loads a full user record by finding their email in the index first."""
        user_id = self.find_user_by_email(email)
        return self.load_user(user_id) if user_id else None

    # =================== DERIVED UPDATE OPERATIONS (FUNCTIONAL) ===================

    def update_user_balance(self, user_id: str, new_balance: float) -> bool:
        """Updates only the total_balance field for a user."""
        def update_balance_func(user_data):
            user_data["total_balance"] = new_balance
            return user_data
        return self.update_user(user_id, update_balance_func) is not None

    def add_wallet_to_user(self, user_id: str, wallet_id: str) -> bool:
        """Adds a wallet ID to a user's wallet list if it's not already present."""
        def add_wallet_func(user_data):
            wallet_ids = user_data.get("wallet_ids", [])
            if wallet_id not in wallet_ids:
                wallet_ids.append(wallet_id)
                user_data["wallet_ids"] = sorted(wallet_ids)
            return user_data
        return self.update_user(user_id, add_wallet_func) is not None

    def remove_wallet_from_user(self, user_id: str, wallet_id: str) -> bool:
        """Removes a wallet ID from a user's wallet list."""
        def remove_wallet_func(user_data):
            wallet_ids = user_data.get("wallet_ids", [])
            if wallet_id in wallet_ids:
                wallet_ids.remove(wallet_id)
                user_data["wallet_ids"] = wallet_ids
            return user_data
        return self.update_user(user_id, remove_wallet_func) is not None

    # =================== UTILITY OPERATIONS ===================

    def rebuild_index_from_records(self) -> Dict[str, Any]:
        """Rebuilds the entire user index from the individual user records."""
        all_user_ids = self.list_users()
        rebuilt_index = {"users": {}}
        index_fields = UserConfig.USER_SCHEMA_VIEWS["index"]
        for user_id in all_user_ids:
            user_data = self.load_user(user_id)
            if user_data:
                index_entry = {field: user_data.get(field) for field in index_fields if field != "user_id"}
                rebuilt_index["users"][user_id] = index_entry
        success = self.save_index_data(rebuilt_index)
        return {"success": success, "rebuilt_count": len(rebuilt_index["users"])}

    def close(self) -> None:
        """Closes the underlying storage provider connection, if applicable."""
        self.provider.close()


if __name__ == "__main__":
    """Simple smoke test: Create one user and ensure user_index.json exists."""
    from pathlib import Path
    from BachiCoin.lib_user.user_storage_factory import UserStorageFactory
    from tests.test_config import dirs

    # Create adapter and ensure index exists
    adapter = UserStorageFactory.create_user_storage(dirs)

    # Save a simple user
    test_user_id = "U123"
    adapter.save_user(test_user_id, {
        "user_id": test_user_id,
        "email_system": "test@example.com"
    })
    print("✅ User saved")

    # Check that the index file exists
    index_file = Path(dirs.user) / f"{USER_INDEX_KEY}.json"
    assert index_file.exists(), f"Expected {index_file} to exist."
    print(f"✅ Index file correctly created at: {index_file}")

    adapter.close()
    print("--- Smoke Test Passed ---")