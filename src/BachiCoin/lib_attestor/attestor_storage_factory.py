#!/usr/bin/env python3
"""attestor_storage_factory.py - A factory for creating AttestorStorageAdapter adapters"""
from datetime import datetime
from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_attestor.attestor_storage_adapter import AttestorStorageAdapter
from BachiCoin.lib_attestor.attestor_config import ATTESTOR_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class AttestorStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_attestor_storage(dirs: Dirs) -> AttestorStorageAdapter:
        """Creates a attestor storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.attestor)
        now = datetime.now().isoformat() + "Z"
        index_init_data = {
            "attestors": {
                "duties_by_epoch": {},
                "duties_by_validator": {},
                "metadata": {
                    "total_duties_assigned": 0,
                    "last_assigned_epoch": -1,
                    "genesis_timestamp": now,
                    "last_updated": now,
                },
            }
        }

        provider = FileStorageProvider(
            str(path),
            index_name=f"{ATTESTOR_INDEX_KEY}.json",
            index_init_data=index_init_data
        )
        return AttestorStorageAdapter(provider)

if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = AttestorStorageFactory.create_attestor_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.attestor}")
    adapter.close()
    print("--- Smoke Test Passed ---")
