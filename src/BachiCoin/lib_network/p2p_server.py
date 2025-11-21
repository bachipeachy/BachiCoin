#!/usr/bin/env python3
"""p2p_server.py - The core P2P server for handling peer-to-peer communication."""

import asyncio
import json
from typing import Dict, Any, Callable, List

from BachiCoin.lib_network.net_config import NetConfig
from BachiCoin.lib_network.net_peer import NetPeer
from BachiCoin.lib_network.net_protocol import MessageType, NetProtocol

class P2PServer:
    """Manages P2P network operations, including peer connections and message routing."""

    def __init__(self, local_node_id: str, host: str, port: int):
        self.local_node_id = local_node_id
        self.host = host
        self.port = port
        self.peers: Dict[str, NetPeer] = {}
        self._server: asyncio.AbstractServer | None = None
        self._running = False
        self._message_handler: Callable[[str, Dict[str, Any]], None] = lambda s, m: None

    def set_message_handler(self, handler_func: Callable[[str, Dict[str, Any]], None]):
        self._message_handler = handler_func

    async def start(self):
        if self._running: return
        self._server = await asyncio.start_server(self._handle_incoming_connection, self.host, self.port)
        self._running = True
        print(f"  [P2P] Server started on {self.host}:{self.port}")
        asyncio.create_task(self._cull_stale_peers())

    async def stop(self):
        if not self._running or not self._server: return
        self._running = False
        self._server.close()
        await self._server.wait_closed()
        await asyncio.gather(*[peer.disconnect() for peer in self.peers.values()])
        self.peers.clear()
        print("  [P2P] Server stopped.")

    async def _handle_incoming_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer_address = writer.get_extra_info('peername')
        try:
            line = await reader.readline()
            if not line: return

            message = json.loads(line.decode())
            msg_uid = message.get("msg_uid", "no-uid")
            print(f"  [P2P] RECV | msg_uid: {msg_uid[:12]} | type: {message.get('type')} | from: {peer_address}")

            if message.get("type") != MessageType.HANDSHAKE.value:
                print(f"  [P2P] ⚠️  First message was not a handshake. Closing.")
                writer.close()
                await writer.wait_closed()
                return

            peer_node_id = message.get("payload", {}).get("node_id")
            if not peer_node_id or peer_node_id == self.local_node_id or peer_node_id in self.peers:
                print(f"  [P2P] ⚠️  Rejecting invalid handshake from {peer_node_id or 'Unknown'}.")
                writer.close()
                await writer.wait_closed()
                return

            if self.local_node_id < peer_node_id:
                print(f"  [P2P] ℹ️  Rejecting incoming from {peer_node_id} (tie-break). They will connect.")
                writer.close()
                await writer.wait_closed()
                return

            peer = NetPeer(peer_node_id, writer)
            peer.update_from_handshake(message.get("payload", {}))
            self.peers[peer_node_id] = peer

            response = NetProtocol.get_handshake_message(self.local_node_id, f"http://{self.host}:{self.port}", self.port, NetConfig.DEFAULT_NETWORK)
            await self.send_message_to_peer(peer_node_id, response)
            
            print(f"  [P2P] 🤝 Accepted connection from {peer_node_id}")
            asyncio.create_task(self._peer_message_loop(peer, reader))

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  [P2P] ⚠️  Could not decode handshake from {peer_address}: {e}. Closing.")
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            print(f"  [P2P] ❌ Error on incoming connection from {peer_address}: {e}")
            if writer and not writer.is_closing():
                writer.close()
                await writer.wait_closed()

    async def _peer_message_loop(self, peer: NetPeer, reader: asyncio.StreamReader):
        try:
            while self._running and peer.is_connected():
                line = await reader.readline()
                if not line: break
                
                message = json.loads(line.decode())
                msg_uid = message.get("msg_uid", "no-uid")
                print(f"  [P2P] RECV | msg_uid: {msg_uid[:12]} | type: {message.get('type')} | from: {peer.node_id[:12]}...")
                await self._dispatch_message(peer.node_id, message)
        
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  [P2P] ⚠️  Protocol error: Could not decode message from {peer.node_id}. Disconnecting peer.")
        except Exception as e:
            print(f"  [P2P] ❌ Unhandled error in message loop for {peer.node_id}: {e}. Disconnecting peer.")
        finally:
            await self.disconnect_peer(peer.node_id)

    async def _dispatch_message(self, sender_id: str, message: Dict):
        peer = self.peers.get(sender_id)
        if not peer: return
        peer.touch()

        if message.get("type") == MessageType.PING.value:
            pong_msg = NetProtocol.get_base_message(MessageType.PONG)
            await self.send_message_to_peer(sender_id, pong_msg)
        elif message.get("type") == MessageType.PONG.value:
            pass
        else:
            if self._message_handler:
                self._message_handler(sender_id, message)

    async def connect_to_outgoing_peer(self, host: str, port: int):
        try:
            print(f"  [P2P] -> Attempting to connect to {host}:{port}...")
            reader, writer = await asyncio.open_connection(host, port)

            handshake = NetProtocol.get_handshake_message(self.local_node_id, f"http://{self.host}:{self.port}", self.port, NetConfig.DEFAULT_NETWORK)
            
            encoded_handshake = json.dumps(handshake).encode() + b'\n'
            writer.write(encoded_handshake)
            await writer.drain()
            msg_uid = handshake.get("msg_uid", "no-uid")
            print(f"  [P2P] SEND | msg_uid: {msg_uid[:12]} | type: {handshake.get('type')} | to: {host}:{port}")

            line = await reader.readline()
            if not line: return

            response = json.loads(line.decode())
            resp_uid = response.get("msg_uid", "no-uid")
            print(f"  [P2P] RECV | msg_uid: {resp_uid[:12]} | type: {response.get('type')} | from: {host}:{port}")

            if response.get("type") != MessageType.HANDSHAKE.value:
                writer.close(); await writer.wait_closed(); return

            peer_node_id = response.get("payload", {}).get("node_id")
            if not peer_node_id or self.local_node_id > peer_node_id:
                writer.close(); await writer.wait_closed(); return

            peer = NetPeer(peer_node_id, writer)
            peer.update_from_handshake(response.get("payload", {}))
            self.peers[peer_node_id] = peer
            print(f"  [P2P] ✅ Connected to peer {peer_node_id}")
            asyncio.create_task(self._peer_message_loop(peer, reader))

        except Exception as e:
            print(f"  [P2P] ❌ Error connecting to {host}:{port}: {e}")

    def get_connected_peer_ids(self) -> List[str]:
        return [peer_id for peer_id, peer in self.peers.items() if peer.is_connected()]

    async def broadcast_message(self, message: Dict[str, Any]):
        msg_uid = message.get("msg_uid", "no-uid")
        msg_type = message.get("type")
        print(f"  [P2P] BCAST | msg_uid: {msg_uid[:12]} | type: {msg_type} | to: {len(self.peers)} peers")
        tasks = [self.send_message_to_peer(peer_id, message) for peer_id in self.peers.keys()]
        await asyncio.gather(*tasks)

    async def send_message_to_peer(self, peer_id: str, message: Dict[str, Any]):
        peer = self.peers.get(peer_id)
        if peer and peer.is_connected() and peer.writer:
            try:
                encoded_message = json.dumps(message).encode() + b'\n'
                peer.writer.write(encoded_message)
                await peer.writer.drain()
                msg_uid = message.get("msg_uid", "no-uid")
                print(f"  [P2P] SEND | msg_uid: {msg_uid[:12]} | type: {message.get('type')} | to: {peer_id[:12]}...")
                return True
            except Exception as e:
                print(f"  [P2P] ❌ Failed to send message to {peer_id}: {e}")
                await self.disconnect_peer(peer_id)
        return False

    async def disconnect_peer(self, peer_id: str):
        if peer_id in self.peers:
            peer = self.peers.pop(peer_id)
            await peer.disconnect()
            print(f"  [P2P] 🔌 Disconnected peer {peer_id}")

    async def _cull_stale_peers(self):
        while self._running:
            await asyncio.sleep(NetProtocol.PING_INTERVAL_SECONDS)
            now = asyncio.get_event_loop().time()
            stale_ids = [p.node_id for p in self.peers.values() if now - p.last_seen.timestamp() > NetConfig.PEER_TIMEOUT_SECONDS]
            for peer_id in stale_ids:
                print(f"  [P2P] 🧹 Culling stale peer {peer_id}")
                await self.disconnect_peer(peer_id)
