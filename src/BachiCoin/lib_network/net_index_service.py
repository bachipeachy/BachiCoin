#!/usr/bin/env python3
"""net_index_service.py — Manage network nodes, peers, and index state."""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable

from BachiCoin.lib_network.net_config import NetConfig
from BachiCoin.lib_network.net_storage_adapter import NetStorageAdapter
from BachiCoin.lib_network.net_validation import NetValidation
from BachiCoin.lib_crossmodule.id_generator import generate_hash_id # Direct import
from BachiCoin.lib_network import net_helper


class NetIndexService:
    """
    Manages node and peer indexing, ensuring that all network participants
    are properly registered, validated, and discoverable through the network index.
    """

    def __init__(self, storage_adapter: NetStorageAdapter, peer_validator_func: Callable[[Dict[str, Any]], bool]):
        self.storage = storage_adapter
        self.validate_peer = peer_validator_func

    def initialize(self):
        """Ensure storage is initialized and rebuild index if needed."""
        self.rebuild_index_from_records()

    def register_node_with_index(self, node_data: Dict[str, Any]) -> Optional[str]:
        """Register a new node, persist it, and add it to the network index."""
        defaults = NetConfig.get_node_defaults()
        defaults.update(node_data)
        node_data = defaults

        # Generate deterministic node_id based on ip_address and p2p_port
        node_id = generate_hash_id("N", {"ip_address": node_data["ip_address"], "p2p_port": node_data["p2p_port"]})
        node_data["node_id"] = node_id

        node_url = node_data.get("node_url")
        if node_url and self.storage.find_node_by_url(node_url):
            print(f"⚠️ Node '{node_url}' already exists. Returning existing node_id.")
            # For idempotency, if node_url exists, return the node_id associated with it.
            # We assume node_url is unique and maps to a single node_id.
            existing_node_id = self.storage.find_node_by_url(node_url)
            # Also ensure the deterministically generated node_id matches the existing one
            if existing_node_id != node_id:
                print(f"⚠️ Mismatch: Deterministic ID {node_id} vs existing ID {existing_node_id} for {node_url}.")
                # This indicates a potential issue with the deterministic ID generation or data corruption.
                # For now, we'll return the existing one, but this might need further investigation.
            return existing_node_id

        # If node_id already exists from a previous run (e.g., persistence), return it for idempotency
        if self.storage.load_node(node_id):
            print(f"⚠️ Node with ID '{node_id}' already exists. Returning existing node_id.")
            return node_id

        now_iso = datetime.now(timezone.utc).isoformat()
        node_data["created_at"] = now_iso
        node_data["last_seen"] = now_iso
        node_data["status"] = node_data.get("status", "active")

        errors = NetValidation.validate_node_data(node_data, "create")
        assert not errors, f"Node validation failed: {errors}"

        if not self.storage.save_node(node_data["node_id"], node_data):
            return None
        if not self._create_index_entry(node_data):
            self.storage.delete_node_with_index(node_data["node_id"])
            return None

        return node_data["node_id"]

    def delete_node_with_index(self, node_id: str) -> bool:
        node_data = self.storage.load_node(node_id)
        assert node_data, f"Cannot delete: Node '{node_id}' not found."

        if not self._remove_index_entry(node_id):
            return False
        if not self.storage.delete_node_with_index(node_id):
            self._create_index_entry(node_data)
            return False
        return True

    def list_nodes(self) -> List[Dict[str, Any]]:
        index = self.storage.load_index_data()
        if not index or "nodes" not in index:
            return []
        return [{"node_id": nid, **info} for nid, info in index["nodes"].items()]

    def get_node_summary(self, node_id: str) -> Optional[Dict[str, Any]]:
        index = self.storage.load_index_data()
        if not index or "nodes" not in index:
            return None
        info = index["nodes"].get(node_id)
        return {"node_id": node_id, **info} if info else None

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_node(node_id)

    def update_node(self, node_id: str, update_data: Dict[str, Any]) -> bool:
        def update_func(node_data):
            node_data.update(update_data)
            node_data["last_seen"] = datetime.now(timezone.utc).isoformat()
            return node_data

        updated_node = self.storage.update_node(node_id, update_func)
        if not updated_node:
            return False

        index_schema_fields = NetConfig.get_node_schema_view("index").keys()
        index_changes = {k: v for k, v in update_data.items() if k in index_schema_fields}
        index_changes["last_seen"] = updated_node["last_seen"]

        return self._update_index_entry(node_id, index_changes)

    def update_node_status(self, node_id: str, new_status: str) -> bool:
        return self.update_node(node_id, {"status": new_status})

    def register_peer(self, node_id: str, peer_data: Dict[str, Any]) -> bool:
        """Add a peer to the node's record and update the network index."""
        node_data = self.storage.load_node(node_id)
        if not node_data:
            return False

        peers = node_data.get("peers", [])
        if not self.validate_peer(peer_data):
            print(f"⚠️ Peer validation failed for {peer_data.get('peer_url')}")
            return False

        if peer_data not in peers:
            peers.append(peer_data)
            return self.update_node(node_id, {"peers": peers})
        return True

    def search_nodes(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        index_data = self.storage.load_index_data()
        if not index_data or "nodes" not in index_data:
            return []

        results = []
        for node_id, node_info in index_data["nodes"].items():
            searchable_text = " ".join(str(node_info.get(field, "")) for field in
                                       ["node_url", "status", "region", "protocol"]
                                       ).lower()
            if query_lower in searchable_text or query_lower in node_id.lower():
                results.append({"node_id": node_id, **node_info})
        return results

    def get_network_stats(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data()
        if not index_data or "nodes" not in index_data:
            return {"total_nodes": 0, "by_status": {}, "total_peers": 0}
        return net_helper.calculate_network_index_stats(index_data["nodes"])

    def rebuild_index_from_records(self) -> Dict[str, Any]:
        # Pass the storage adapter to the helper function
        return net_helper.rebuild_index_from_records(self.storage.list_nodes(), self.storage)

    def _create_index_entry(self, node_data: Dict[str, Any]) -> bool:
        entry = net_helper.create_index_entry(node_data)

        def add_func(index_data):
            index_data.setdefault("nodes", {})[node_data["node_id"]] = entry
            return index_data

        return self.storage.update_index_data(add_func) is not None

    def _update_index_entry(self, node_id: str, changes: Dict[str, Any]) -> bool:
        def update_func(index_data):
            if "nodes" in index_data and node_id in index_data["nodes"]:
                index_data["nodes"][node_id].update(changes)
            return index_data

        return self.storage.update_index_data(update_func) is not None

    def _remove_index_entry(self, node_id: str) -> bool:
        def remove_func(index_data):
            return net_helper.remove_index_entry(index_data, node_id)
        return self.storage.update_index_data(remove_func) is not None

    def close(self) -> None:
        self.storage.close()


if __name__ == "__main__":
    pass
