#!/usr/bin/env python3
"""wallet_index_service.py -- delegates business logic to wallet_helper for clarity and separation of concerns."""

from typing import Dict, Any, List, Optional

from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_wallet import wallet_helper
from BachiCoin.lib_wallet.wallet_config import get_wallet_schema_view, WalletConfig
from BachiCoin.lib_wallet.wallet_storage_adapter import WalletStorageAdapter


class WalletIndexService:
    """Service orchestrating wallet lifecycle and index management."""

    def __init__(self, storage_adapter: WalletStorageAdapter, user_service: UserIndexService):
        assert storage_adapter, "WalletStorageAdapter instance is required."
        assert user_service, "UserIndexService instance is required."
        self.storage = storage_adapter
        self.user_service = user_service

    def create_wallet_with_index(self, user_id: str, wallet_data: Dict[str, Any], addresses: Dict[str, Any]) -> Optional[str]:
        user_wallets = self.list_wallets_by_user(user_id)
        if len(user_wallets) >= WalletConfig.MAX_WALLET_COUNT:
            print(f"⚠️ User {user_id} has reached the maximum wallet limit.")
            return None

        # wallet_helper.prepare_wallet_data now generates the wallet_id deterministically
        full_wallet_data = wallet_helper.prepare_wallet_data(user_id, wallet_data, addresses)
        wallet_helper.validate_wallet_before_creation(full_wallet_data)

        wallet_id = full_wallet_data["wallet_id"]

        # Check if a wallet with this deterministic ID already exists
        if self.storage.load_wallet(wallet_id):
            print(f"⚠️ Wallet with ID '{wallet_id}' already exists for user '{user_id}'.")
            return wallet_id # Return existing wallet_id for idempotency

        if not self.storage.save_wallet(wallet_id, full_wallet_data):
            return None

        if not wallet_helper.create_index_entry(full_wallet_data, self.storage):
            self.storage.delete_wallet_with_index(wallet_id)
            return None

        self.user_service.add_wallet_to_user(user_id, wallet_id)
        return wallet_id

    def delete_wallet_with_index(self, wallet_id: str) -> bool:
        wallet_data = self.storage.load_wallet(wallet_id)
        assert wallet_data, f"Cannot delete: Wallet '{wallet_id}' not found."
        user_id = wallet_data.get("user_id")

        if not wallet_helper.remove_index_entry(wallet_id, self.storage):
            return False

        if not self.storage.delete_wallet_with_index(wallet_id):
            wallet_helper.create_index_entry(wallet_data, self.storage)
            return False

        if user_id:
            self.user_service.remove_wallet_from_user(user_id, wallet_id)
        return True

    def list_wallets(self, wallet_type: str = None, status: str = None, user_id: str = None) -> List[Dict[str, Any]]:
        index_data = self.storage.load_index_data()
        if not index_data or "wallets" not in index_data:
            return []

        results = []
        for wallet_id, wallet_info in index_data["wallets"].items():
            if wallet_type and wallet_info.get("wallet_type") != wallet_type:
                continue
            if status and wallet_info.get("status") != status:
                continue
            if user_id and wallet_info.get("user_id") != user_id:
                continue
            results.append({"wallet_id": wallet_id, **wallet_info})
        return results

    def get_wallet_summary(self, wallet_id: str) -> Optional[Dict[str, Any]]:
        index_data = self.storage.load_index_data()
        if not index_data or "wallets" not in index_data:
            return None
        info = index_data["wallets"].get(wallet_id)
        return {"wallet_id": wallet_id, **info} if info else None

    def get_wallet(self, wallet_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_wallet(wallet_id)

    def list_wallets_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        index_data = self.storage.load_index_data()
        if not index_data or "wallets" not in index_data:
            return []
        return [{"wallet_id": wid, **info} for wid, info in index_data["wallets"].items() if
                info.get("user_id") == user_id]

    def get_wallet_id_by_address(self, address: str) -> Optional[str]:
        for wallet_id in self.storage.list_wallet_ids():
            wallet_data = self.storage.load_wallet(wallet_id)
            if wallet_data and "addresses" in wallet_data:
                for addr_info in wallet_data["addresses"].values():
                    if addr_info.get("address") == address:
                        return wallet_id
        return None

    def update_wallet(self, wallet_id: str, update_data: Dict[str, Any]) -> bool:
        success = wallet_helper.update_wallet_state(self.storage, wallet_id, update_data)
        if not success:
            return False

        updated_wallet = self.storage.load_wallet(wallet_id)
        index_schema_fields = get_wallet_schema_view("index").keys()
        index_changes = {k: v for k, v in update_data.items() if k in index_schema_fields}
        index_changes["last_modified"] = updated_wallet["last_modified"]

        return wallet_helper.update_index_entry(wallet_id, index_changes, self.storage)

    def update_account_state(self, wallet_id: str, balance: Optional[float] = None,
                             nonce: Optional[int] = None) -> bool:
        return wallet_helper.update_account_state(self.storage, wallet_id, balance, nonce)

    def reconcile_user_balance(self, user_id: str) -> bool:
        """Calculates a user's total balance by summing their wallets and updates the user record."""
        user_summary = self.user_service.get_user_summary(user_id)
        if not user_summary:
            return False

        wallet_ids = user_summary.get("wallet_ids", [])
        if not wallet_ids:
            return self.user_service.update_user_balance(user_id, 0.0)

        total_balance = 0.0
        for wid in wallet_ids:
            wallet_summary = self.get_wallet_summary(wid)
            if wallet_summary:
                total_balance += wallet_summary.get("balance", 0.0)

        return self.user_service.update_user_balance(user_id, total_balance)

    def search_wallets(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        index_data = self.storage.load_index_data()
        if not index_data or "wallets" not in index_data:
            return []

        results = []
        for wallet_id, wallet_info in index_data["wallets"].items():
            searchable_text = " ".join(str(wallet_info.get(field, "")) for field in
                                       ["name", "wallet_type", "currency", "user_id", "status"]).lower()
            if query_lower in searchable_text or query_lower in wallet_id.lower():
                results.append({"wallet_id": wallet_id, **wallet_info})
        return results

    def get_wallet_stats(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data()
        if not index_data or "wallets" not in index_data:
            return {"total_wallets": 0, "by_type": {}, "by_currency": {}, "total_balance": 0.0}

        wallets = index_data["wallets"]
        stats = {"total_wallets": len(wallets), "by_type": {}, "by_currency": {}, "total_balance": 0.0}

        for wallet_info in wallets.values():
            wallet_type = wallet_info.get("wallet_type", "unknown")
            stats["by_type"][wallet_type] = stats["by_type"].get(wallet_type, 0) + 1
            currency = wallet_info.get("currency", "unknown")
            stats["by_currency"][currency] = stats["by_currency"].get(currency, 0) + 1
            stats["total_balance"] += float(wallet_info.get("balance", 0.0))
        return stats

    def rebuild_wallet_index(self) -> Dict[str, Any]:
        all_wallet_ids = self.storage.list_wallet_ids()
        rebuilt_index = {"wallets": {}}
        processed, errors = 0, 0

        for wallet_id in all_wallet_ids:
            wallet_data = self.storage.load_wallet(wallet_id)
            if wallet_data:
                index_fields = get_wallet_schema_view("index").keys()
                entry = {field: wallet_data.get(field) for field in index_fields}
                entry["address_count"] = len(wallet_data.get("addresses", {}))
                entry["available_address_types"] = list(wallet_data.get("addresses", {}).keys())
                rebuilt_index["wallets"][wallet_id] = entry
                processed += 1
            else:
                errors += 1

        success = self.storage.save_index_data(rebuilt_index)
        return {"success": success, "processed": processed, "errors": errors,
                "total_wallets_scanned": len(all_wallet_ids)}

    def close(self):
        self.storage.close()
