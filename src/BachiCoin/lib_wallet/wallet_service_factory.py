#!/usr/bin/env python3
"""wallet_service_factory.py - creates a WalletIndexService using a unified storage backend with dependency injection"""

from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_wallet.wallet_storage_factory import WalletStorageFactory
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_user.user_index_service import UserIndexService
from typing import Optional
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


class WalletServiceFactory:
    """Factory to create a WalletIndexService with dependency injection."""

    @with_dirs
    @staticmethod
    def create_wallet_index_service(dirs: Dirs, user_service: Optional[UserIndexService] = None) -> WalletIndexService:
        """Creates a WalletIndexService and its required dependencies."""

        if user_service is None:
            user_service = UserServiceFactory.create_user_index_service(dirs)
        
        wallet_storage_adapter = WalletStorageFactory.create_wallet_storage(dirs)
        wallet_service = WalletIndexService(
            storage_adapter=wallet_storage_adapter,
            user_service=user_service
        )
        return wallet_service


if __name__ == "__main__":
    from tests.test_config import dirs

    wallet_service = WalletServiceFactory.create_wallet_index_service(dirs)
    print(f"✅ {wallet_service}\nwith storage at {dirs.wallet}")
    print("--- Smoke Test Passed ---")
