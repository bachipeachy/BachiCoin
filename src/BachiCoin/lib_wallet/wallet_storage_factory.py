#!/usr/bin/env python3
"""wallet_storage_factory.py - A factory for creating WalletStorageAdapter adapters"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_wallet.wallet_storage_adapter import WalletStorageAdapter
from BachiCoin.lib_wallet.wallet_config import WALLET_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class WalletStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_wallet_storage(dirs: Dirs) -> WalletStorageAdapter:
        """Creates a wallet storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.wallet)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{WALLET_INDEX_KEY}.json",
            index_init_data={"wallets": {}}
        )
        return WalletStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = WalletStorageFactory.create_wallet_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.wallet}")
    adapter.close()
    print("--- Smoke Test Passed ---")
