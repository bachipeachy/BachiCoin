#!/usr/bin/env python3
"""user_index_service.py --  manage user functions and data."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from BachiCoin.lib_crossmodule.id_generator import generate_hash_id
from BachiCoin.lib_user import user_helper
from BachiCoin.lib_user.user_config import UserConfig
from BachiCoin.lib_user.user_storage_adapter import UserStorageAdapter
from BachiCoin.lib_user.user_validation import UserValidation


class UserIndexService:
    """Manages user business logic and indexing while delegating pure logic to user_helper."""

    def __init__(self, storage_adapter: UserStorageAdapter):
        self.storage = storage_adapter

    def initialize(self):
        """Ensure storage is ready + rebuild index from records."""
        self.rebuild_index_from_records()

    # =================== CORE USER LIFECYCLE ===================

    def create_user_with_index(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Creates a new user record from public data."""
        defaults = UserConfig.get_user_full_defaults()
        defaults.update(user_data)
        user_data = defaults

        email = user_data.get("email_registration")
        if email and self.storage.find_user_by_email(email):
            print(f"⚠️ User with email '{email}' already exists.")
            existing_user_id = self.storage.find_user_by_email(email)
            return {"user_id": existing_user_id}

        now_iso = datetime.now(timezone.utc).isoformat()
        # Use the new deterministic ID generator
        user_data["user_id"] = generate_hash_id("U", {"email_registration": user_data["email_registration"]})
        user_data["created_at"] = now_iso
        user_data["last_modified"] = now_iso
        user_data["kyc_key"] = (
            f"{user_data.get('first_name', '')}|"
            f"{user_data.get('last_name', '')}|"
            f"{user_data.get('email_registration', '')}"
        )
        if not user_data.get("email_current"):
            user_data["email_current"] = user_data.get("email_registration")

        errors = UserValidation.validate_user_data(user_data, "create")
        assert not errors, f"User creation validation failed: {errors}"

        if not self.storage.save_user(user_data["user_id"], user_data):
            return None
        if not self._create_index_entry(user_data):
            self.storage.delete_user_with_index(user_data["user_id"])
            return None

        return {"user_id": user_data["user_id"]}

    def delete_user_with_index(self, user_id: str) -> bool:
        user_data = self.storage.load_user(user_id)
        assert user_data, f"Cannot delete: User '{user_id}' not found."
        assert not user_data.get("wallet_ids"), f"Cannot delete: User '{user_id}' still has associated wallets."

        if not self._remove_index_entry(user_id):
            return False
        if not self.storage.delete_user_with_index(user_id):
            self._create_index_entry(user_data)
            return False
        return True

    # =================== DATA RETRIEVAL ===================

    def list_users(self) -> List[Dict[str, Any]]:
        index = self.storage.load_index_data()
        if not index or "users" not in index:
            return []
        return [{"user_id": uid, **info} for uid, info in index["users"].items()]

    def get_user_summary(self, user_id: str) -> Optional[Dict[str, Any]]:
        index = self.storage.load_index_data()
        if not index or "users" not in index:
            return None
        info = index["users"].get(user_id)
        return {"user_id": user_id, **info} if info else None

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_user(user_id)

    # =================== UPDATE ===================

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        def update_func(user_data):
            user_data.update(update_data)
            user_data["last_modified"] = datetime.now(timezone.utc).isoformat()
            return user_data

        updated_user = self.storage.update_user(user_id, update_func)
        if not updated_user:
            return False

        index_schema_fields = UserConfig.get_user_schema_view("index").keys()
        index_changes = {k: v for k, v in update_data.items() if k in index_schema_fields}
        index_changes["last_modified"] = updated_user["last_modified"]

        return self._update_index_entry(user_id, index_changes)

    def update_user_balance(self, user_id: str, new_balance: float) -> bool:
        return self.update_user(user_id, {"total_balance": new_balance})

    def add_wallet_to_user(self, user_id: str, wallet_id: str) -> bool:
        user_data = self.storage.load_user(user_id)
        if not user_data: return False
        wallet_ids = user_data.get("wallet_ids", [])
        if wallet_id not in wallet_ids:
            wallet_ids.append(wallet_id)
            return self.update_user(user_id, {"wallet_ids": sorted(wallet_ids)})
        return True

    def remove_wallet_from_user(self, user_id: str, wallet_id: str) -> bool:
        user_data = self.storage.load_user(user_id)
        if not user_data: return True
        wallet_ids = user_data.get("wallet_ids", [])
        if wallet_id in wallet_ids:
            wallet_ids.remove(wallet_id)
            return self.update_user(user_id, {"wallet_ids": wallet_ids})
        return True

    # =================== SEARCH + ANALYTICS ===================

    def search_users(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        index_data = self.storage.load_index_data()
        if not index_data or "users" not in index_data:
            return []

        results = []
        for user_id, user_info in index_data["users"].items():
            searchable_text = " ".join(str(user_info.get(field, "")) for field in
                                       ["first_name", "last_name", "email_current", "user_type", "status"]
                                       ).lower()
            if query_lower in searchable_text or query_lower in user_id.lower():
                results.append({"user_id": user_id, **user_info})
        return results

    def get_user_stats(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data()
        if not index_data or "users" not in index_data:
            return {"total_users": 0, "by_type": {}, "by_status": {}, "total_balance": 0.0, "total_wallets": 0}
        return user_helper.calculate_user_index_stats(index_data["users"])

    # =================== MAINTENANCE ===================

    def rebuild_index_from_records(self) -> Dict[str, Any]:
        return user_helper.rebuild_index_from_records(self.storage.list_users(), self.storage)

    # =================== INDEX WRAPPERS ===================

    def _create_index_entry(self, user_data: Dict[str, Any]) -> bool:
        entry = user_helper.create_index_entry(user_data)

        def add_func(index_data):
            index_data.setdefault("users", {})[user_data["user_id"]] = entry
            return index_data

        return self.storage.update_index_data(add_func) is not None

    def _update_index_entry(self, user_id: str, changes: Dict[str, Any]) -> bool:
        def update_func(index_data):
            if "users" in index_data and user_id in index_data["users"]:
                index_data["users"][user_id].update(changes)
            return index_data

        return self.storage.update_index_data(update_func) is not None

    def _remove_index_entry(self, user_id: str) -> bool:
        def remove_func(index_data):
            return user_helper.remove_index_entry(index_data, user_id)

        return self.storage.update_index_data(remove_func) is not None

    def close(self) -> None:
        self.storage.close()


if __name__ == "__main__":
    pass
