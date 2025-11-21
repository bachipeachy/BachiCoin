#!/usr/bin/env python3
"""net_storage_adapter.py - Provides a backend-agnostic storage adapter for network data"""

from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_network.net_config import NET_INDEX_KEY

class NetStorageAdapter:
    """Delegates all I/O operations to a pluggable storage provider."""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== CORE NODE I/O OPERATIONS ===================

    def save_node(self, node_id: str, node_data: Dict[str, Any]) -> bool:
        """Saves a complete node data object."""
        return self.provider.save(node_id, node_data)

    def load_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Loads a complete node data object by its ID."""
        return self.provider.load(node_id)

    def update_node(self, node_id: str, update_func: Callable[[Dict], Dict]) -> Optional[Dict[str, Any]]:
        """Atomically updates a node record using a functional pattern."""
        return self.provider.update(node_id, update_func)

    def delete_node_with_index(self, node_id: str) -> bool:
        """Deletes a node record by its ID."""
        return self.provider.delete(node_id)

    def node_exists(self, node_id: str) -> bool:
        """Checks if a node record exists."""
        return self.provider.exists(node_id)

    def list_nodes(self) -> List[str]:
        """Lists all node IDs in the storage."""
        return [key for key in self.provider.list_keys() if key != NET_INDEX_KEY]

    # =================== INDEX I/O OPERATIONS ===================

    def save_index_data(self, index_data: Dict[str, Any]) -> bool:
        """Saves the entire network index object."""
        return self.provider.save(NET_INDEX_KEY, index_data)

    def load_index_data(self, ) -> Optional[Dict[str, Any]]:
        """Loads the entire network index object."""
        return self.provider.load(NET_INDEX_KEY)

    def update_index_data(self, update_func: Callable[[Dict], Dict]) -> Optional[Dict[str, Any]]:
        """Atomically updates the network index using a functional pattern.
        Initializes with an empty dict if it doesn't exist.
        """
        current_data = self.load_index_data()
        if current_data is None:
            current_data = {}
        
        updated_data = update_func(current_data)
        self.save_index_data(updated_data)
        return updated_data

    # =================== DERIVED QUERY OPERATIONS (INDEX-BASED) ===================

    def find_node_by_url(self, node_url: str) -> Optional[str]:
        """Finds a node ID by its URL from the index."""
        index_data = self.load_index_data()
        if not index_data or "nodes" not in index_data:
            return None

        url_lower = node_url.lower()
        for node_id, node_info in index_data["nodes"].items():
            if node_info.get("node_url", "").lower() == url_lower:
                return node_id
        return None

    # =================== UTILITY OPERATIONS ===================

    def close(self) -> None:
        """Closes the underlying storage provider connection, if applicable."""
        self.provider.close()


if __name__ == "__main__":
    """Simple smoke test to verify the adapter can be initialized."""
    from BachiCoin.lib_storage.file_provider import FileStorageProvider
    from tests.test_config import dirs # Import dirs from test_config

    # 1. Initialize the adapter using the provided dirs
    provider = FileStorageProvider(dirs.net, NET_INDEX_KEY)
    adapter = NetStorageAdapter(provider)
    print("✅ Adapter initialized successfully.")

    # 2. Save and load a node
    test_node_id = "N12345678901234567890"
    node_data = {"node_id": test_node_id, "node_url": "http://test.com"}
    adapter.save_node(test_node_id, node_data)
    loaded_node = adapter.load_node(test_node_id)
    assert loaded_node == node_data, "Save/Load operation failed."
    print("✅ Node saved and loaded successfully.")

    # 3. Update the index
    def add_to_index(index):
        index.setdefault("nodes", {})[test_node_id] = {"node_url": "http://test.com"}
        return index

    adapter.update_index_data(add_to_index)
    index_data = adapter.load_index_data()
    assert index_data["nodes"][test_node_id]["node_url"] == "http://test.com", "Index update failed."
    print("✅ Index updated and loaded successfully.")

    # 4. Find node by URL
    found_id = adapter.find_node_by_url("http://test.com")
    assert found_id == test_node_id, "Find by URL failed."
    print("✅ Node found by URL successfully.")

    # 5. Close the adapter
    adapter.close()
    print("✅ Adapter closed successfully.")

    print("\n--- NetStorageAdapter Smoke Test Passed Successfully! ---")
