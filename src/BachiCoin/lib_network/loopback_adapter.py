#!/usr/bin/env python3
"""loopback_adapter.py - A simulated network adapter for in-process multi-node testing."""

import asyncio
import os
import sys
from typing import Dict, Any, Callable, List

# --- System Path Setup ---
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from BachiCoin.lib_network.net_base_adapter import NetBaseAdapter

LOOPBACK_REGISTRY: Dict[str, 'LoopbackAdapter'] = {}

class LoopbackAdapter(NetBaseAdapter):
    """A simulated network adapter that routes messages between nodes in the same process."""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._message_handler: Callable[[str, Dict[str, Any]], None] = lambda s, m: print("  [Loopback] ⚠️  No message handler registered!")
        LOOPBACK_REGISTRY[self.node_id] = self
        print(f"  [Loopback] Adapter for node {self.node_id[:12]}... registered.")

    async def start(self):
        print(f"  [Loopback] Adapter for {self.node_id[:12]}... started.")
        await asyncio.sleep(0)

    async def stop(self):
        del LOOPBACK_REGISTRY[self.node_id]
        print(f"  [Loopback] Adapter for {self.node_id[:12]}... stopped and deregistered.")
        await asyncio.sleep(0)

    def register_message_handler(self, handler_func: Callable[[str, Dict[str, Any]], None]):
        self._message_handler = handler_func

    def handle_incoming_message(self, sender_id: str, message: Dict[str, Any]):
        self._message_handler(sender_id, message)

    async def send(self, sender_id: str, receiver_id: str, message: Dict[str, Any]):
        target_adapter = LOOPBACK_REGISTRY.get(receiver_id)
        if target_adapter:
            # msg_uid = message.get("msg_uid", "no-uid")
            # msg_type = message.get("type")
            # print(f"  [Loopback] ROUTE | msg_uid: {msg_uid[:12]} | type: {msg_type} | from: {sender_id[:6]}... | to: {receiver_id[:6]}...")
            target_adapter.handle_incoming_message(sender_id, message)
        else:
            print(f"  [Loopback] ⚠️  Attempted to send message to unknown peer: {receiver_id}")

    async def broadcast(self, sender_id: str, message: Dict[str, Any]):
        # msg_uid = message.get("msg_uid", "no-uid")
        # msg_type = message.get("type")
        # print(f"  [Loopback] BCAST | msg_uid: {msg_uid[:12]} | type: {msg_type} | from: {sender_id[:12]}...")
        tasks = [
            self.send(sender_id, peer_id, message)
            for peer_id in LOOPBACK_REGISTRY if peer_id != sender_id
        ]
        await asyncio.gather(*tasks)

# =================== SMOKE TEST ===================

if __name__ == "__main__":

    async def smoke_test_loopback_adapter():
        """A simple smoke test to verify the new LoopbackAdapter functionality."""
        print("--- LoopbackAdapter Smoke Test ---")

        received_messages: Dict[str, List] = {"NodeA": [], "NodeB": [], "NodeC": []}

        def create_handler(node_id: str):
            def handler(sender_id: str, msg: Dict[str, Any]):
                print(f"  - MockNode {node_id} received a message from {sender_id}.")
                received_messages[node_id].append(msg)
            return handler

        adapter_a = LoopbackAdapter("NodeA")
        adapter_b = LoopbackAdapter("NodeB")
        adapter_c = LoopbackAdapter("NodeC")
        
        adapter_a.register_message_handler(create_handler("NodeA"))
        adapter_b.register_message_handler(create_handler("NodeB"))
        adapter_c.register_message_handler(create_handler("NodeC"))

        print("\n--- Testing Broadcast ---")
        test_message = {"type": "TEST_GOSSIP", "msg_uid": "trace-123", "payload": {"data": "hello world"}}
        await adapter_a.broadcast(adapter_a.node_id, test_message)

        assert len(received_messages["NodeB"]) == 1
        assert received_messages["NodeB"][0]["msg_uid"] == "trace-123"
        print("✅ Broadcast delivered correctly.")

        print("\n--- Testing Direct Send ---")
        direct_message = {"type": "DIRECT_MSG", "msg_uid": "trace-456", "payload": {"secret": "for your eyes only"}}
        await adapter_c.send(adapter_c.node_id, adapter_a.node_id, direct_message)

        assert len(received_messages["NodeA"]) == 1
        assert received_messages["NodeA"][0]["msg_uid"] == "trace-456"
        print("✅ Direct message delivered correctly.")
        
        await adapter_a.stop()
        await adapter_b.stop()
        await adapter_c.stop()

        print("\n--- LoopbackAdapter Smoke Test Passed! ---")

    LOOPBACK_REGISTRY.clear()
    asyncio.run(smoke_test_loopback_adapter())
