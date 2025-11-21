#!/usr/bin/env python3
"""mempool_storage_factory.py - A factory for creating MempoolStorageAdapter adapters"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_mempool.mempool_storage_adapter import MempoolStorageAdapter
from BachiCoin.lib_mempool.mempool_config import MEMPOOL_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class MempoolStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_mempool_storage(dirs: Dirs) -> MempoolStorageAdapter:
        """Creates a mempool storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.mempool)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{MEMPOOL_INDEX_KEY}.json",
            index_init_data={"mempools": {}}
        )
        return MempoolStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = MempoolStorageFactory.create_mempool_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.mempool}")
    adapter.close()
    print("--- Smoke Test Passed ---")
