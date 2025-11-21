#!/usr/bin/env python3
"""finalizer_storage_adapter.py - Provides a backend-agnostic storage adapter for finalizer data"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_finalizer.finalizer_config import FINALIZER_INDEX_KEY


class FinalizerStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== FINALIZER INDEX OPERATIONS ===================

    def save_finalizer_index(self, index_data: Dict[str, Any]) -> bool:
        """Saves the main finalizer index."""
        return self.provider.save(FINALIZER_INDEX_KEY, index_data)

    def load_finalizer_index(self) -> Dict[str, Any]:
        """Loads the main finalizer index, returning an empty dict if not found."""
        return self.provider.load(FINALIZER_INDEX_KEY) or {}

    def update_finalizer_index(self, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates the main finalizer index."""
        return self.provider.update(FINALIZER_INDEX_KEY, update_func)

    # =================== INDIVIDUAL CHECKPOINT OPERATIONS ===================

    def save_checkpoint(self, epoch: int, checkpoint_data: Dict[str, Any]) -> bool:
        """Saves an individual checkpoint record, keyed by its epoch."""
        return self.provider.save(f"checkpoint_{epoch}", checkpoint_data)

    def load_checkpoint(self, epoch: int) -> Optional[Dict[str, Any]]:
        """Loads an individual checkpoint record by its epoch."""
        return self.provider.load(f"checkpoint_{epoch}")

    def update_checkpoint(self, epoch: int, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates an individual checkpoint record."""
        return self.provider.update(f"checkpoint_{epoch}", update_func)

    def delete_checkpoint(self, epoch: int) -> bool:
        """Deletes an individual checkpoint record by its epoch."""
        return self.provider.delete(f"checkpoint_{epoch}")

    def list_checkpoint_epochs(self) -> List[int]:
        """Lists all checkpoint epochs based on stored checkpoint files."""
        return sorted([
            int(key.replace("checkpoint_", ""))
            for key in self.provider.list_keys()
            if key.startswith("checkpoint_") and key.replace("checkpoint_", "").isdigit()
        ])

    def close(self) -> None:
        """Closes the underlying storage provider connection."""
        self.provider.close()


if __name__ == "__main__":
    """Unit test for the FinalizerStorageAdapter."""
    from BachiCoin.lib_finalizer.finalizer_storage_factory import FinalizerStorageFactory
    from tests.test_config import dirs

    print("=== FinalizerStorageAdapter Unit Test ===")

    # 1. Create adapter and ensure index exists
    adapter = FinalizerStorageFactory.create_finalizer_storage(dirs)
    print(f"{adapter}\nstores data at {dirs.finalizer}")

    print("\n🧪 Testing index operations...")
    test_index = {"metadata": {"finalized_epoch": -1}, "checkpoints": {}}
    assert adapter.save_finalizer_index(test_index), "Failed to save index"
    loaded_index = adapter.load_finalizer_index()
    assert loaded_index == test_index, "Loaded index does not match saved index"
    print("✅ Index operations successful.")

    print("\n🧪 Testing individual checkpoint operations...")
    test_epoch = 100
    checkpoint_data = {"epoch": test_epoch, "root": "0x" + "f" * 64, "status": "justified"}
    assert adapter.save_checkpoint(test_epoch, checkpoint_data), "Failed to save checkpoint"
    loaded_checkpoint = adapter.load_checkpoint(test_epoch)
    assert loaded_checkpoint == checkpoint_data, "Loaded checkpoint does not match"
    assert adapter.list_checkpoint_epochs() == [test_epoch], "Checkpoint epoch not found in list"
    print("✅ Individual checkpoint operations successful.")

    adapter.close()
    print("\n✅ FinalizerStorageAdapter Test Complete!")