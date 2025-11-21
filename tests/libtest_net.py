#!/usr/bin/env python3
"""libtest_net.py - Integration tests for both P2P and Loopback adapters."""

import asyncio
import shutil
from typing import List, Dict, Any

from BachiCoin.api_public import net_lib_api
from tests.test_config import dirs

NODE_PORTS = [9333, 9334, 9335]

# =================== MOCK MEMPOOL SERVICE ===================

class MockMempoolService:
    """A mock service to capture messages for verification and satisfy NetNode dependency."""
    def __init__(self):
        self.received_txs: List[Dict[str, Any]] = []
        self.network_broadcaster = None # NetNode will assign its broadcast method here

    async def handle_network_tx(self, tx_payload: Dict[str, Any]):
        self.received_txs.append(tx_payload)

# =================== P2P ADAPTER TEST ===================

async def connect_with_tiebreak(node_a: net_lib_api.NetNode, port_a: int, node_b: net_lib_api.NetNode, port_b: int):
    """Connects two nodes, respecting the P2P server's tie-breaking rule."""
    host = "127.0.0.1"
    if node_a.node_id < node_b.node_id:
        await net_lib_api.connect_to_peer(node_a, host, port_b)
    else:
        await net_lib_api.connect_to_peer(node_b, host, port_a)

async def test_p2p_network():
    """Tests P2P-specific features like connection and peer discovery."""
    print("=" * 70)
    print("🎯 Testing P2P Adapter Network")
    print("=" * 70)
    
    nodes: List[net_lib_api.NetNode] = []
    mock_mempool_services = [MockMempoolService() for _ in NODE_PORTS] # Create mocks

    try:
        print("\nPHASE 1: Creating and starting all nodes...")
        for i, port in enumerate(NODE_PORTS):
            # Pass the mock mempool_service to create_net_node
            node = net_lib_api.create_net_node(dirs, "127.0.0.1", port, mock_mempool_services[i], adapter_type="p2p")
            nodes.append(node)
        await asyncio.gather(*(net_lib_api.start(node) for node in nodes))
        print("✅ All nodes are running.")

        print("\nPHASE 2: Interconnecting nodes...")
        await connect_with_tiebreak(nodes[0], NODE_PORTS[0], nodes[1], NODE_PORTS[1])
        await connect_with_tiebreak(nodes[1], NODE_PORTS[1], nodes[2], NODE_PORTS[2])
        await asyncio.sleep(1)

        print("\nPHASE 3: Verifying peer discovery...")
        peers_of_node1 = net_lib_api.get_connected_peers(nodes[1])
        assert nodes[0].node_id in peers_of_node1 and nodes[2].node_id in peers_of_node1
        print("✅ Peer discovery successful.")

    finally:
        if nodes:
            print("\nPHASE 4: Shutting down all nodes...")
            await asyncio.gather(*(net_lib_api.stop(node) for node in nodes))
            print("✅ All nodes stopped successfully.")

# =================== LOOPBACK ADAPTER TEST ===================

async def test_loopback_network():
    """Tests Loopback-specific features like in-process message routing."""
    print("\n" + "=" * 70)
    print("🎯 Testing Loopback Adapter Network")
    print("=" * 70)

    nodes: List[net_lib_api.NetNode] = []
    mock_mempool_services = [MockMempoolService() for _ in NODE_PORTS] # Create mocks

    try:
        net_lib_api.LOOPBACK_REGISTRY.clear()
        print("\nPHASE 1: Creating and starting all nodes...")
        for i, port in enumerate(NODE_PORTS):
            # Pass the mock mempool_service to create_net_node
            node = net_lib_api.create_net_node(dirs, "127.0.0.1", port, mock_mempool_services[i], adapter_type="loopback")
            node.mempool_service = mock_mempool_services[i] # Assign for handle_incoming_message
            nodes.append(node)
        await asyncio.gather(*(net_lib_api.start(node) for node in nodes))
        print("✅ All nodes are running.")

        print("\nPHASE 2: Testing broadcast messaging...")
        tx_broadcast = {"tx_hash": "BROADCAST_123"}
        await nodes[0].broadcast(net_lib_api.MessageType.TRANSACTION, tx_broadcast)
        await asyncio.sleep(0.1)

        assert len(mock_mempool_services[1].received_txs) == 1
        assert mock_mempool_services[1].received_txs[0]["tx_hash"] == "BROADCAST_123"
        print("✅ Broadcast message correctly received by other nodes.")

        print("\nPHASE 3: Testing direct messaging...")
        tx_direct = {"tx_hash": "DIRECT_456"}
        await nodes[2].send_direct_message(nodes[0].node_id, net_lib_api.MessageType.TRANSACTION, tx_direct)
        await asyncio.sleep(0.1)

        assert len(mock_mempool_services[0].received_txs) == 1
        assert mock_mempool_services[0].received_txs[0]["tx_hash"] == "DIRECT_456"
        print("✅ Direct message correctly received by target node.")
        
    finally:
        if nodes:
            print("\nPHASE 4: Shutting down all nodes...")
            await asyncio.gather(*(net_lib_api.stop(node) for node in nodes))
            print("✅ All nodes stopped successfully.")

# =================== MAIN ORCHESTRATOR ===================

async def main():
    # Clean up any previous run before starting
    if dirs.net.exists():
        shutil.rmtree(dirs.net)
    dirs.net.mkdir()
    
    await test_p2p_network()
    
    # Clean up the net directory between tests for better isolation
    if dirs.net.exists():
        shutil.rmtree(dirs.net)
    dirs.net.mkdir()

    await test_loopback_network()
    
    print("\n" + "=" * 70)
    print("🎉 ALL NETWORK INTEGRATION TESTS COMPLETED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
