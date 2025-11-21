#!/usr/bin/env python3
"""blockchain_storage_factory.py - A factory for creating BlockchainStorageAdapter adapters"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_blockchain.blockchain_storage_adapter import BlockchainStorageAdapter
from BachiCoin.lib_blockchain.blockchain_config import BLOCKCHAIN_INDEX_KEY, get_initial_index_structure
from BachiCoin.lib_crossmodule.dirs import Dirs


class BlockchainStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_blockchain_storage(dirs: Dirs) -> BlockchainStorageAdapter:
        """Creates a blockchain storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.blockchain)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{BLOCKCHAIN_INDEX_KEY}.json",
            index_init_data=get_initial_index_structure()
        )
        return BlockchainStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = BlockchainStorageFactory.create_blockchain_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.blockchain}")
    adapter.close()
    print("--- Smoke Test Passed ---")
