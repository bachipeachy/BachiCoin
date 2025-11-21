#!/usr/bin/env python3
"""blockchain_service_factory.py - creates a BlockchainIndexService using a unified storage backend with dependency injection"""

from BachiCoin.lib_blockchain.blockchain_storage_factory import BlockchainStorageFactory
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


class BlockchainServiceFactory:
    """Factory to create a BlockchainIndexService with dependency injection."""

    @with_dirs
    @staticmethod
    def create_blockchain_index_service(dirs: Dirs) -> BlockchainIndexService:
        """Creates a BlockchainIndexService and its required dependencies."""

        blockchain_storage_adapter = BlockchainStorageFactory.create_blockchain_storage(dirs)
        blockchain_service = BlockchainIndexService(
            storage_adapter=blockchain_storage_adapter
        )
        return blockchain_service


if __name__ == "__main__":
    from tests.test_config import dirs

    blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(dirs)
    print(f"✅ {blockchain_service}\nwith storage at {dirs.blockchain}")
    print("--- Smoke Test Passed ---")
