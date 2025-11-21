#!/usr/bin/env python3
"""net_storage_factory.py - A factory for creating NetStorageAdapter instances"""

from pathlib import Path
from BachiCoin.lib_storage.file_provider import FileStorageProvider
from BachiCoin.lib_network.net_storage_adapter import NetStorageAdapter
from BachiCoin.lib_network.net_config import NET_INDEX_KEY
from BachiCoin.lib_crossmodule.dirs import Dirs

class NetStorageFactory:
    """A factory for creating and configuring network storage adapters."""

    @staticmethod
    def create_net_storage(dirs: Dirs) -> NetStorageAdapter:
        """Creates a network storage adapter using the FileStorageProvider backend."""
        path = Path(dirs.net)
        provider = FileStorageProvider(
            str(path),
            index_name=f"{NET_INDEX_KEY}.json",
            index_init_data={"nodes": {}}  # Initialize with an empty nodes dictionary
        )
        return NetStorageAdapter(provider)


if __name__ == "__main__":
    """Simple smoke test to verify the factory creates an adapter."""
    from tests.test_config import dirs

    # Create the adapter using the factory
    adapter = NetStorageFactory.create_net_storage(dirs)
    
    # Verify the adapter and its configuration
    print(f"Successfully created adapter: {adapter}")
    print(f"Adapter will store data at: {dirs.net}")
    
    # Test a basic operation
    adapter.load_index_data() # This should not fail
    print("✅ Successfully loaded initial index data.")

    adapter.close()
    print("--- Smoke Test Passed ---")
