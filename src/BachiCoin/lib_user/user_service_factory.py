#!/usr/bin/env python3
"""user_service_factory.py - creates a UserIndexService using a unified storage backend with dependency injection"""

from BachiCoin.lib_user.user_storage_factory import UserStorageFactory
from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


class UserServiceFactory:
    """Factory to create UserIndexService with its dependencies."""

    @with_dirs
    @staticmethod
    def create_user_index_service(dirs: Dirs) -> UserIndexService:
        """Creates UserIndexService using a unified storage backend."""
        storage_adapter = UserStorageFactory.create_user_storage(dirs)
        service = UserIndexService(
            storage_adapter=storage_adapter
        )
        service.initialize()
        return service


if __name__ == "__main__":
    from tests.test_config import dirs

    user_service = UserServiceFactory.create_user_index_service(dirs)
    print(f"✅ {user_service} with storage at {dirs.user}")
    print("--- Smoke Test Passed ---")
