#!/usr/bin/env python3
"""tx_storage_adapter.py - provides low-level CRUD operations for transaction data and its index."""

from typing import Dict, Any, Optional, List

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_transaction.tx_config import TX_INDEX_KEY


class TxStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""
    def __init__(self, provider: StorageProvider):
        self.provider = provider

    # =================== CORE TRANSACTION RECORD OPERATIONS ===================

    def save_tx(self, tx_hash: str, tx_data: Dict[str, Any]) -> bool:
        """Save a full transaction record identified by its hash."""
        return self.provider.save(tx_hash, tx_data)

    def load_tx(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Load a full transaction record by its hash."""
        return self.provider.load(tx_hash)

    def update_tx(self, tx_hash: str, update_func) -> Optional[Dict[str, Any]]:
        """The `update_func` modifies transaction data (dict)."""
        return self.provider.update(tx_hash, update_func)

    def delete_tx(self, tx_hash: str) -> bool:
        """Delete a full transaction record by its hash."""
        return self.provider.delete(tx_hash)

    def tx_exists(self, tx_hash: str) -> bool:
        """Check if a transaction record exists for the given hash."""
        return self.provider.exists(tx_hash)

    def list_tx_hashes(self) -> List[str]:
        """List all transaction hashes (keys) currently stored, excluding the index."""
        return [key for key in self.provider.list_keys() if key != f"{TX_INDEX_KEY}.json"]

    # =================== TRANSACTION INDEX OPERATIONS ===================

    def save_index_data(self, index_data: Dict[str, Any]) -> bool:
        """Save the entire transaction index data."""
        return self.provider.save(TX_INDEX_KEY, index_data)

    def load_index_data(self) -> Optional[Dict[str, Any]]:
        """Load the entire transaction index data."""
        return self.provider.load(TX_INDEX_KEY)

    def close(self) -> None:
        """Close the underlying storage connection."""
        self.provider.close()


if __name__ == '__main__':
    """
    A simple smoke test to verify that the adapter can be initialized"""
    import shutil
    import tempfile
    from datetime import datetime
    from pathlib import Path

    from BachiCoin.lib_storage.storage_config import StorageType
    # Import the factory to test the real application flow
    from BachiCoin.lib_transaction.tx_storage_factory import TxStorageFactory
    from tests.test_config import dirs

    print("--- Running TxStorageAdapter + Factory Smoke Test ---")

    temp_dir = tempfile.mkdtemp()
    print(f"✅ Created temporary directory for testing: {temp_dir}")

    try:
        # 1. Create adapter via the factory (the correct way)
        adapter = TxStorageFactory.create_tx_storage(dirs)
        print("✅ Adapter created successfully via factory.")

        # 2. Ensure index exists and check file creation
        index_file = Path(dirs.tx) / f"{TX_INDEX_KEY}.json"
        assert index_file.exists(), f"Expected index file {index_file} was not created."
        print(f"✅ Index file correctly created at: {index_file}")

        # 3. Test basic I/O operations
        test_tx_hash = "0x123abc"
        test_tx_data = {
            "tx_hash": test_tx_hash,
            "from_address": "0xsender",
            "created_at": datetime.now().isoformat()
        }

        assert adapter.save_tx(test_tx_hash, test_tx_data), "Save operation failed."
        loaded_tx = adapter.load_tx(test_tx_hash)
        assert loaded_tx == test_tx_data, "Loaded data does not match saved data."
        print("✅ Save and Load operations successful.")

        # 4. Test list_tx_hashes excludes the index
        all_hashes = adapter.list_tx_hashes()
        assert test_tx_hash in all_hashes, "list_tx_hashes should include the new tx."
        assert TX_INDEX_KEY not in all_hashes, "list_tx_hashes should not include the index key."
        print("✅ list_tx_hashes works correctly.")

        adapter.close()
        print("✅ Adapter closed successfully.")

    finally:
        shutil.rmtree(temp_dir)
        print(f"✅ Cleaned up temporary directory: {temp_dir}")

    print("\n--- Smoke Test Passed Successfully! ---")
