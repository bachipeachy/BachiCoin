#!/usr/bin/env python3
"""finalizer_storage_factory.py - A factory for creating FinalizerStorageAdapter adapters"""
from datetime import datetime
from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_finalizer.finalizer_storage_adapter import FinalizerStorageAdapter
from BachiCoin.lib_finalizer.finalizer_config import FINALIZER_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class FinalizerStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_finalizer_storage(dirs: Dirs) -> FinalizerStorageAdapter:
        """Creates a finalizer storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.finalizer)
        now = datetime.now().isoformat() + "Z"
        index_init_data = {
            "finalizers": {
                "checkpoints": {},
                "metadata": {
                    "justified_epoch": -1,
                    "finalized_epoch": -1,
                    "genesis_timestamp": now,
                    "last_updated": now,
                },
            }
        }

        provider = FileStorageProvider(
            str(path),
            index_name=f"{FINALIZER_INDEX_KEY}.json",
            index_init_data=index_init_data
        )
        return FinalizerStorageAdapter(provider)

if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = FinalizerStorageFactory.create_finalizer_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.finalizer}")
    adapter.close()
    print("--- Smoke Test Passed ---")
