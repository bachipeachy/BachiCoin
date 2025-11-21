#!/usr/bin/env python3
"""net_node.py - The main orchestrator for a BachiCoin network node."""

import asyncio
from typing import Optional, Dict, Any, List

from BachiCoin.lib_crossmodule.dirs import Dirs
from BachiCoin.lib_network.net_base_adapter import NetBaseAdapter
from BachiCoin.lib_network.net_index_service import NetIndexService
from BachiCoin.lib_network.net_protocol import MessageType, NetProtocol
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService

class NetNode:
    """A class representing the local BachiCoin node and its network participation."""

    def __init__(self, dirs: Dirs, network_adapter: NetBaseAdapter, net_service: NetIndexService, node_id: str, mempool_service: MempoolIndexService):
        self.dirs = dirs
        self.network_adapter = network_adapter
        self.net_service = net_service
        self.node_id = node_id
        self.mempool_service = mempool_service # Injected mempool_service
        self.blockchain_service: Optional[Any] = None
        self.network_adapter.register_message_handler(self.handle_incoming_message)
        print(f"📦 Node initialized with ID: {self.node_id}")

    async def start(self):
        print(f"  -> Starting node {self.node_id[:12]}...")
        await self.network_adapter.start()

    async def stop(self):
        print(f"  -> Stopping node {self.node_id[:12]}...")
        await self.network_adapter.stop()
        self.net_service.close()

    def handle_incoming_message(self, sender_id: str, msg: Dict[str, Any]):
        """Routes an incoming message from the network to the correct service."""
        msg_type = msg.get("type")
        msg_uid = msg.get("msg_uid", "no-uid")
        payload = msg.get("payload", {})
        
        service_name = "Unknown"
        if msg_type == MessageType.TRANSACTION.value and self.mempool_service:
            # service_name = self.mempool_service.__class__.__name__
            # print(f"  [Node] HANDOFF | msg_uid: {msg_uid[:12]} | type: {msg_type} | to: {service_name}")
            asyncio.create_task(self.mempool_service.handle_network_tx(payload))
        elif msg_type == MessageType.NEW_BLOCK.value and self.blockchain_service:
            # service_name = self.blockchain_service.__class__.__name__
            # print(f"  [Node] HANDOFF | msg_uid: {msg_uid[:12]} | type: {msg_type} | to: {service_name}")
            # asyncio.create_task(self.blockchain_service.handle_network_block(payload))
            pass
        else:
            print(f"  [Node] ⚠️  No handler for message type '{msg_type}' (msg_uid: {msg_uid[:12]}).")

    async def broadcast(self, msg_type: MessageType, payload: Dict[str, Any]):
        """Builds a message and broadcasts it to the network via the adapter."""
        message = NetProtocol.get_base_message(msg_type, payload)
        # msg_uid = message.get("msg_uid", "no-uid")
        # print(f"  [Node] ORIGIN | msg_uid: {msg_uid[:12]} | type: {msg_type.value} | mode: broadcast")
        await self.network_adapter.broadcast(self.node_id, message)

    async def send_direct_message(self, receiver_id: str, msg_type: MessageType, payload: Dict[str, Any]):
        """Builds a message and sends it to a specific peer via the adapter."""
        message = NetProtocol.get_base_message(msg_type, payload)
        # msg_uid = message.get("msg_uid", "no-uid")
        # print(f"  [Node] ORIGIN | msg_uid: {msg_uid[:12]} | type: {msg_type.value} | mode: direct | to: {receiver_id[:12]}...")
        await self.network_adapter.send(self.node_id, receiver_id, message)

    # --- P2P Passthrough Methods ---

    async def connect_to_peer(self, host: str, port: int):
        if hasattr(self.network_adapter, 'connect_to_peer'):
            await self.network_adapter.connect_to_peer(host, port)
        else:
            print(f"  [Node] ⚠️  Adapter does not support explicit peer connections.")

    def get_connected_peers(self) -> List[str]:
        if hasattr(self.network_adapter, 'get_connected_peers'):
            return self.network_adapter.get_connected_peers()
        return []
