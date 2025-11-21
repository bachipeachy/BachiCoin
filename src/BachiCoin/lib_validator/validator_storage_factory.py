#!/usr/bin/env python3
"""validator_storage_factory.py - Factory for creating validator storage adapters."""
from pathlib import Path

from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_validator.validator_storage_adapter import ValidatorStorageAdapter
from BachiCoin.lib_validator.validator_config import VALIDATOR_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs

class ValidatorStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_validator_storage(dirs: Dirs) -> ValidatorStorageAdapter:
        """Creates a validator storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.validator)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{VALIDATOR_INDEX_KEY}.json",
            index_init_data={"validators": {}}
        )
        return ValidatorStorageAdapter(provider)


if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = ValidatorStorageFactory.create_validator_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.validator}")
    adapter.close()
    print("--- Smoke Test Passed ---")
