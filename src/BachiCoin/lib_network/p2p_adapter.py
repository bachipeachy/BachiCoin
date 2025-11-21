#!/usr/bin/env python3
"""p2p_adapter.py - A concrete implementation of the NetBaseAdapter for P2P networking."""

import asyncio
import os
import sys
from typing import Dict, Any, Callable, List

# --- System Path Setup ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from BachiCoin.lib_network.net_base_adapter import NetBaseAdapter
from BachiCoin.lib_network.p2p_server import P2PServer

class P2PAdapter(NetBaseAdapter):
    """The production network adapter that uses a P2PServer for real network communication."""

    def __init__(self, host: str, port: int, node_id: str):
        self.node_id = node_id
        self._p2p_server = P2PServer(node_id, host, port)
        self._message_handler: Callable[[str, Dict[str, Any]], None] = lambda s, m: None

    async def start(self):
        """Starts the underlying P2P server."""
        print(f"  [P2P] Adapter for {self.node_id[:12]}... starting.")
        self._p2p_server.set_message_handler(self._message_handler)
        await self._p2p_server.start()

    async def stop(self):
        """Stops the underlying P2P server."""
        print(f"  [P2P] Adapter for {self.node_id[:12]}... stopping.")
        await self._p2p_server.stop()

    def register_message_handler(self, handler_func: Callable[[str, Dict[str, Any]], None]):
        """Registers the callback that the P2PServer will use for incoming messages."""
        self._message_handler = handler_func

    async def send(self, sender_id: str, receiver_id: str, message: Dict[str, Any]):
        """Sends a direct message to a specific peer."""
        print(f"  [P2P] Sending message from {sender_id[:12]}... to {receiver_id[:12]}... (Type: {message.get('type')})")
        await self._p2p_server.send_message_to_peer(receiver_id, message)

    async def broadcast(self, sender_id: str, message: Dict[str, Any]):
        """Broadcasts a message to all connected peers."""
        print(f"  [P2P] Broadcasting message from {sender_id[:12]}... (Type: {message.get('type')})")
        await self._p2p_server.broadcast_message(message)

    # --- P2P-Specific Methods ---

    async def connect_to_peer(self, host: str, port: int):
        """Initiates an outgoing connection from this node to another peer."""
        await self._p2p_server.connect_to_outgoing_peer(host, port)

    def get_connected_peers(self) -> List[str]:
        """Returns a list of node IDs for all currently connected peers."""
        return self._p2p_server.get_connected_peer_ids()

# =================== SMOKE TEST ===================

if __name__ == "__main__":
    # This smoke test is conceptual. To run it, you would need two separate processes.

    async def smoke_test_p2p_adapter():
        """A simple smoke test to verify the P2PAdapter can be instantiated and run."""
        print("--- P2PAdapter Smoke Test ---")
        
        node_id_a = "NODE_A_1234567890"
        adapter_a = P2PAdapter("127.0.0.1", 9998, node_id_a)

        node_id_b = "NODE_B_0987654321" # Must be higher for tie-break
        adapter_b = P2PAdapter("127.0.0.1", 9999, node_id_b)

        # 2. Register handlers
        received_a = []
        received_b = []
        def handler_a(sender, msg): received_a.append((sender, msg))
        def handler_b(sender, msg): received_b.append((sender, msg))
        adapter_a.register_message_handler(handler_a)
        adapter_b.register_message_handler(handler_b)

        # 3. Start adapters
        await adapter_a.start()
        await adapter_b.start()
        print("\n✅ Adapters started.")

        # 4. Test connection
        await adapter_a.connect_to_peer("127.0.0.1", 9999) # A connects to B
        await asyncio.sleep(0.1) # Allow time for connection
        assert len(adapter_a.get_connected_peers()) == 1
        assert len(adapter_b.get_connected_peers()) == 1
        print("\n✅ Peer connection successful.")

        # 5. Test broadcast
        broadcast_msg = {"type": "GOSSIP", "data": "hello from A"}
        await adapter_a.broadcast(node_id_a, broadcast_msg)
        await asyncio.sleep(0.1) # Allow time for message transit
        assert len(received_b) == 1
        assert received_b[0][0] == node_id_a
        assert received_b[0][1]["data"] == "hello from A"
        print("\n✅ Broadcast message received.")

        # 6. Test direct send
        direct_msg = {"type": "DIRECT", "secret": "secret for A"}
        await adapter_b.send(node_id_b, node_id_a, direct_msg)
        await asyncio.sleep(0.1) # Allow time for message transit
        assert len(received_a) == 1
        assert received_a[0][0] == node_id_b
        assert received_a[0][1]["secret"] == "secret for A"
        print("\n✅ Direct message received.")

        # 7. Stop adapters
        await adapter_a.stop()
        await adapter_b.stop()
        print("\n✅ Adapters stopped.")

        print("\n--- P2PAdapter Smoke Test Passed! ---")

    asyncio.run(smoke_test_p2p_adapter())
