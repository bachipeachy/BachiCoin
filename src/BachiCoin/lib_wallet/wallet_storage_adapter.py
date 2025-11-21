#!/usr/bin/env python3
"""wallet_storage_adapter.py - Provides a backend-agnostic storage adapter for data"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_wallet.wallet_config import WALLET_INDEX_KEY


class WalletStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== CORE WALLET OPERATIONS ===================

    def save_wallet(self, wallet_id: str, wallet_data: Dict[str, Any]) -> bool:
        """Saves a complete wallet data object."""
        return self.provider.save(wallet_id, wallet_data)

    def load_wallet(self, wallet_id: str) -> Optional[Dict[str, Any]]:
        """Loads a complete wallet data object by its ID."""
        return self.provider.load(wallet_id)

    def update_wallet(self, wallet_id: str, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates a wallet using a functional pattern."""
        return self.provider.update(wallet_id, update_func)

    def delete_wallet_with_index(self, wallet_id: str) -> bool:
        """Deletes a wallet record by its ID."""
        return self.provider.delete(wallet_id)

    def wallet_exists(self, wallet_id: str) -> bool:
        """Checks for the existence of a wallet by its ID."""
        return self.provider.exists(wallet_id)

    def list_wallet_ids(self) -> List[str]:
        """Lists the IDs of all existing wallets, excluding the index key."""
        return [key for key in self.provider.list_keys() if key != WALLET_INDEX_KEY]

    # =================== INDEX OPERATIONS ===================

    def save_index_data(self, index_data: Dict[str, Any]) -> bool:
        """Saves the entire wallet index object."""
        return self.provider.save(WALLET_INDEX_KEY, index_data)

    def load_index_data(self) -> Optional[Dict[str, Any]]:
        """Loads the entire wallet index object."""
        return self.provider.load(WALLET_INDEX_KEY)

    def update_index_data(self, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates the wallet index using a functional pattern."""
        return self.provider.update(WALLET_INDEX_KEY, update_func)
    # =================== WALLET-SPECIFIC QUERIES ===================

    def find_wallet_id_by_address(self, address: str) -> Optional[str]:
        """Finds a wallet ID by an address contained within it."""
        index_data = self.load_index_data()
        if not index_data or "wallets" not in index_data:
            return None

        for wallet_id, wallet_info in index_data["wallets"].items():
            # The index should store addresses for efficient lookup
            addresses = wallet_info.get("addresses", {})
            if any(addr.get("address") == address for addr in addresses.values()):
                return wallet_id
        return None

    def adjust_wallet_balance(self, wallet_id: str, new_balance: float, new_nonce: Optional[int] = None) -> bool:
        """A specialized, efficient update for a wallet's balance and nonce."""

        def update_balance_func(wallet_data: Dict[str, Any]) -> Dict[str, Any]:
            wallet_data["balance"] = new_balance
            if new_nonce is not None:
                wallet_data["nonce"] = new_nonce
            wallet_data["last_modified"] = self._get_current_timestamp()
            return wallet_data

        result = self.update_wallet(wallet_id, update_balance_func)
        return result is not None

    # =================== UTILITY OPERATIONS ===================

    def get_storage_stats(self) -> Dict[str, Any]:
        """Retrieves statistics about the wallet storage."""
        wallet_ids = self.list_wallet_ids()
        index_data = self.load_index_data()
        indexed_count = len(index_data.get("wallets", {})) if index_data else 0

        return {
            "total_wallets": len(wallet_ids),
            "indexed_wallets": indexed_count,
            "index_consistent": len(wallet_ids) == indexed_count,
            "storage_provider": self.provider.__class__.__name__
        }

    def close(self) -> None:
        """Closes the connection to the underlying storage provider."""
        self.provider.close()

    # =================== PRIVATE HELPER METHODS ===================

    @staticmethod
    def _get_current_timestamp() -> str:
        """Returns the current time as a UTC ISO 8601 string."""
        return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    """A minimal smoke test to verify class instantiation and basic properties."""
    from tests.test_config import dirs
    from BachiCoin.lib_wallet.wallet_storage_factory import WalletStorageFactory

    adapter = WalletStorageFactory.create_wallet_storage(dirs)
    print(f"adapter: {adapter}\nwill store data at {dirs.wallet}")
    print("\n--- Smoke Test Passed Successfully! ---")
