#!/usr/bin/env python3
"""tx_service_factory.py - creates a TxIndexService using a unified storage backend with dependency injection"""

from BachiCoin.lib_transaction.tx_index_service import TxIndexService
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_transaction.tx_storage_factory import TxStorageFactory
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from typing import Optional


class TxServiceFactory:
    """Factory for creating a TxIndexService."""

    @with_dirs
    @staticmethod
    def create_tx_index_service(dirs: Dirs, wallet_index_service: Optional[WalletIndexService] = None) -> TxIndexService:

        if wallet_index_service is None:
            wallet_index_service = WalletServiceFactory.create_wallet_index_service(dirs)
        storage_adapter = TxStorageFactory.create_tx_storage(dirs)
        service = TxIndexService(
            storage_adapter=storage_adapter,
            wallet_index_service=wallet_index_service
        )

        return service


if __name__ == "__main__":
    from tests.test_config import dirs

    tx_service = TxServiceFactory.create_tx_index_service(dirs)
    print(f"✅ {tx_service} with storage at {dirs.tx}")
    print("--- Smoke Test Passed ---")
