#!/usr/bin/env python3
"""tx_storage_factory.py - A factory for creating TxStorageAdapter adapters"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_transaction.tx_storage_adapter import TxStorageAdapter
from BachiCoin.lib_transaction.tx_config import TX_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class TxStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_tx_storage(dirs: Dirs) -> TxStorageAdapter:
        """Creates a tx storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.tx)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{TX_INDEX_KEY}.json",
            index_init_data={"txs": {}}
        )
        return TxStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = TxStorageFactory.create_tx_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.tx}")
    adapter.close()
    print("--- Smoke Test Passed ---")
