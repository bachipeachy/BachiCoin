#!/usr/bin/env python3
"""net_lib_api.py - Public API façade for the entire Network module."""

from typing import Dict, Any, List, Optional

from BachiCoin.api_public.dirs_api import Dirs
from BachiCoin.lib_network.net_node import NetNode as _NetNode
NetNode = _NetNode

# --- Expose Enums and Configs for public consumption ---
from BachiCoin.lib_network.net_config import NodeType, NodeStatus
from BachiCoin.lib_network.net_protocol import MessageType
from BachiCoin.lib_network.loopback_adapter import LOOPBACK_REGISTRY as _LOOPBACK_REGISTRY
LOOPBACK_REGISTRY = _LOOPBACK_REGISTRY

# Import the factory function from the correct location
from BachiCoin.lib_network.net_service_factory import NetServiceFactory
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService



# =================== FACTORY FUNCTION ===================

def create_net_node(dirs: Dirs, host: str, port: int, mempool_service: MempoolIndexService, adapter_type: str = "loopback") -> NetNode:
    """Factory function to create a NetNode with a selectable network adapter."""
    return NetServiceFactory.create_net_node(dirs, host, port, mempool_service, adapter_type=adapter_type)

# =================== FROM net_node.py ===================

async def start(node: NetNode):
    """Starts the node's network adapter."""
    await node.start()

async def stop(node: NetNode):
    """Stops the node's network adapter and closes services."""
    await node.stop()

async def connect_to_peer(node: NetNode, host: str, port: int):
    """Initiates an outgoing connection from this node to another peer."""
    await node.connect_to_peer(host, port)

def get_local_node_data(node: NetNode) -> Optional[Dict[str, Any]]:
    """Retrieves the full data record for the local node."""
    if not node:
        return None
    
    data = {
        "node_id": node.node_id,
        "adapter_type": node.network_adapter.__class__.__name__,
    }
    
    # P2P adapter has host and port, Loopback does not
    if hasattr(node.network_adapter, 'host'):
        data['host'] = node.network_adapter.host
    if hasattr(node.network_adapter, 'port'):
        data['port'] = node.network_adapter.port
        
    return data

def get_connected_peers(node: NetNode) -> List[str]:
    """Returns a list of node IDs for all currently connected peers."""
    return node.get_connected_peers()

# =================== FROM net_index_service.py ===================

# These functions are now correctly exposed as part of the public API
# and operate on the NetNode instance provided by the caller.

# =================== SMOKE TEST ===================

if __name__ == "__main__":
    """A simple smoke test for the public Network API."""
    import asyncio
    from tests.test_config import dirs
    from BachiCoin.lib_network.loopback_adapter import LOOPBACK_REGISTRY
    from BachiCoin.api_public.mempool_lib_api import create_mempool_index_service

    async def main():
        print("--- Running Network API Smoke Test ---")

        # 1. Create a loopback node (default)
        print("\n--- Testing Loopback Node Creation (Default) ---")
        LOOPBACK_REGISTRY.clear()
        mempool_service = create_mempool_index_service(dirs)
        node_loopback = create_net_node(dirs, "127.0.0.1", 9333, mempool_service=mempool_service)
        print(f"✅ Loopback NetNode created successfully with ID: {node_loopback.node_id}")
        await start(node_loopback)

        # 2. Test API wrappers
        local_data = get_local_node_data(node_loopback)
        assert local_data["node_id"] == node_loopback.node_id
        print("✅ get_local_node_data successful.")

        await stop(node_loopback)
        print("✅ Loopback node lifecycle tested.")

        # 3. Create a P2P node (explicit)
        print("\n--- Testing P2P Node Creation ---")
        node_p2p = create_net_node(dirs, "127.0.0.1", 9334, mempool_service=mempool_service, adapter_type="p2p")
        print(f"✅ P2P NetNode created successfully with ID: {node_p2p.node_id}")
        await start(node_p2p)
        await stop(node_p2p)
        print("✅ P2P node lifecycle tested.")

        print("\n--- Smoke Test Passed Successfully! ---")

    asyncio.run(main())
