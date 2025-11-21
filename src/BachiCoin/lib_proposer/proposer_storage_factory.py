#!/usr/bin/env python3
"""proposer_storage_factory.py - A factory for creating ProposerStorageAdapter adapters"""
from datetime import datetime
from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_proposer.proposer_storage_adapter import ProposerStorageAdapter
from BachiCoin.lib_proposer.proposer_config import PROPOSER_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs


class ProposerStorageFactory:
    """A factory for creating and configuring storage providers and adapters."""

    @staticmethod
    def create_proposer_storage(dirs: Dirs) -> ProposerStorageAdapter:
        """Creates a proposer storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.proposer)
        now = datetime.now().isoformat() + "Z"
        index_init_data = {
            "proposers": {
                "duties_by_slot": {},
                "duties_by_epoch": {},
                "metadata": {
                    "total_duties_assigned": 0,
                    "last_assigned_slot": -1,
                    "genesis_timestamp": now,
                    "last_updated": now,
                },
            }
        }

        provider = FileStorageProvider(
            str(path),
            index_name=f"{PROPOSER_INDEX_KEY}.json",
            index_init_data=index_init_data
        )
        return ProposerStorageAdapter(provider)

if __name__ == "__main__":
    from tests.test_config import dirs

    adapter = ProposerStorageFactory.create_proposer_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.proposer}")
    adapter.close()
    print("--- Smoke Test Passed ---")
