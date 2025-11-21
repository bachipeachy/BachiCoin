#!/usr/bin/env python3
"""net_peer.py - Represents a single connected peer in the network."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional

class PeerStatus(Enum):
    """Defines the connection status of a peer."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

class NetPeer:
    """Represents a stateful connection to another node in the network."""

    def __init__(self, node_id: str, writer: asyncio.StreamWriter):
        self.node_id = node_id
        self.writer = writer
        self.status: PeerStatus = PeerStatus.CONNECTING
        self.last_seen: datetime = datetime.now(timezone.utc)
        self.protocol_version: Optional[str] = None
        self.node_url: Optional[str] = None # Populated from handshake

    def update_from_handshake(self, handshake_payload: Dict[str, Any]):
        """Updates peer information from a handshake message."""
        self.protocol_version = handshake_payload.get("protocol_version")
        self.node_url = handshake_payload.get("node_url")
        self.status = PeerStatus.CONNECTED
        self.touch()

    def touch(self):
        """Updates the last_seen timestamp for the peer."""
        self.last_seen = datetime.now(timezone.utc)

    def is_connected(self) -> bool:
        """Checks if the peer is currently connected."""
        return self.status == PeerStatus.CONNECTED and self.writer and not self.writer.is_closing()

    async def disconnect(self):
        """Marks the peer as disconnected and closes the writer stream."""
        if self.status == PeerStatus.DISCONNECTED:
            return
        self.status = PeerStatus.DISCONNECTED
        if self.writer and not self.writer.is_closing():
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass # Ignore errors on close, we just want it closed

    def __repr__(self) -> str:
        return f"<NetPeer id={self.node_id} status={self.status.value}>"
