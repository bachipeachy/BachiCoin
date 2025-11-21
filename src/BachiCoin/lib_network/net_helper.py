#!/usr/bin/env python3
"""net_helper.py - Helper functions for the network module."""

from typing import Dict, Any, List
from BachiCoin.lib_network.net_config import NetConfig

def calculate_network_index_stats(nodes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Calculates statistics from the network index."""
    stats = {
        "total_nodes": len(nodes),
        "by_status": {},
        "total_peers": 0
    }

    for node_info in nodes.values():
        status = node_info.get("status", "unknown")
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
        # Assuming 'peers' in index entry is a count or can be derived
        # For now, we'll just count the number of nodes as potential peers
        stats["total_peers"] += len(node_info.get("peers", [])) # This might need adjustment based on actual index content

    return stats

def rebuild_index_from_records(all_node_ids: List[str], storage) -> Dict[str, Any]:
    """Rebuilds the index from all node records in storage."""
    rebuilt_index = {"nodes": {}}
    processed, errors = 0, 0

    for node_id in all_node_ids:
        node_data = storage.load_node(node_id)
        if node_data:
            entry = create_index_entry(node_data)
            rebuilt_index["nodes"][node_id] = entry
            processed += 1
        else:
            errors += 1

    success = storage.save_index_data(rebuilt_index)
    return {"success": success, "processed": processed, "errors": errors,
            "total_nodes_scanned": len(all_node_ids)}

def create_index_entry(node_data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a summary entry for the index from full node data."""
    index_fields = NetConfig.get_node_schema_view("index").keys()
    # Exclude 'node_id' from the entry itself as it's used as the key in the index dictionary
    return {field: node_data.get(field) for field in index_fields if field != "node_id"}

def remove_index_entry(index_data: Dict[str, Any], node_id: str) -> Dict[str, Any]:
    """Removes a node entry from the index."""
    if "nodes" in index_data and node_id in index_data["nodes"]:
        del index_data["nodes"][node_id]
    return index_data
