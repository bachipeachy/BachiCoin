#!/usr/bin/env python3
"""user_storage_factory.py - A factory for creating UserStorageAdapter adapters"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_user.user_storage_adapter import UserStorageAdapter
from BachiCoin.lib_user.user_config import USER_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class UserStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_user_storage(dirs: Dirs) -> UserStorageAdapter:
        """Creates a user storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.user)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{USER_INDEX_KEY}.json",
            index_init_data={"users": {}}
        )
        return UserStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = UserStorageFactory.create_user_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.user}")
    adapter.close()
    print("--- Smoke Test Passed ---")