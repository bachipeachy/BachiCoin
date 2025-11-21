#!/usr/bin/env python3
"""net_protocol.py - Defines network communication protocols, message types, and handshakes."""

import uuid
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from BachiCoin.lib_crypto.crypto_utils import CryptoUtils

class MessageType(Enum):
    """Defines the types of messages exchanged on the network."""
    HANDSHAKE = "handshake"
    PING = "ping"
    PONG = "pong"
    GET_PEERS = "get_peers"
    PEERS = "peers"
    GET_BLOCK = "get_block"
    BLOCK = "block"
    TRANSACTION = "transaction"
    NEW_NODE_ANNOUNCE = "new_node_announce"
    NEW_BLOCK = "new_block"

class ProtocolVersion(Enum):
    """Defines supported network protocol versions."""
    V1 = "1.0"

class NetProtocol:
    """A pure configuration class defining network protocol constants and message structures."""

    PROTOCOL_MAGIC_NUMBER = 0xBAC1C01
    DEFAULT_PROTOCOL_VERSION = ProtocolVersion.V1.value
    HANDSHAKE_TIMEOUT_SECONDS = 5
    PING_INTERVAL_SECONDS = 30

    GENERIC_MESSAGE_SCHEMA: Dict[str, Any] = {
        "magic": {"type": int, "required": True},
        "version": {"type": str, "required": True},
        "type": {"type": str, "required": True, "allowed_values": [mt.value for mt in MessageType]},
        "timestamp": {"type": str, "required": True, "format": "iso8601"},
        "msg_uid": {"type": str, "required": True}, # Unique ID for tracing
        "payload": {"type": dict, "required": False, "default": {}}
    }

    @classmethod
    def get_base_message(cls, message_type: MessageType, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Constructs a base message with a unique ID for tracing."""
        ts = datetime.now(timezone.utc)
        unique_str = f"{ts.timestamp()}-{uuid.uuid4()}"
        # Use the approved crypto library for hashing with a supported algorithm
        msg_uid = CryptoUtils.hash_data(unique_str, algo="sha256").hex()[:12] # Changed algo to sha256
        
        return {
            "magic": cls.PROTOCOL_MAGIC_NUMBER,
            "version": cls.DEFAULT_PROTOCOL_VERSION,
            "type": message_type.value,
            "timestamp": ts.isoformat(),
            "msg_uid": msg_uid,
            "payload": payload or {}
        }

    @classmethod
    def get_handshake_message(cls, node_id: str, node_url: str, p2p_port: int, network_type: str) -> Dict[str, Any]:
        """Constructs a standard handshake message using the base message factory."""
        payload = {
            "node_id": node_id,
            "node_url": node_url,
            "p2p_port": p2p_port,
            "protocol_version": cls.DEFAULT_PROTOCOL_VERSION,
            "network_type": network_type
        }
        return cls.get_base_message(MessageType.HANDSHAKE, payload)


if __name__ == "__main__":
    """A simple smoke test to verify that the protocol module can be loaded."""
    print("--- Running NetProtocol Smoke Test ---")
    
    handshake_msg = NetProtocol.get_handshake_message(
        node_id="NTEST123", node_url="http://test.com", p2p_port=9333, network_type="testnet"
    )
    print(f"✅ Generated Handshake Message: {handshake_msg}")
    
    assert handshake_msg["type"] == MessageType.HANDSHAKE.value
    assert "node_id" in handshake_msg["payload"]
    print("✅ Standard fields are correct.")

    assert "msg_uid" in handshake_msg and len(handshake_msg["msg_uid"]) == 12
    print(f"✅ Message UID for tracing is present: {handshake_msg['msg_uid']}")

    tx_msg = NetProtocol.get_base_message(MessageType.TRANSACTION, {"tx_hash": "abc"})
    assert tx_msg["type"] == MessageType.TRANSACTION.value
    assert "msg_uid" in tx_msg
    print(f"✅ Base message created for TRANSACTION type with UID: {tx_msg['msg_uid']}")

    print("\n--- NetProtocol Smoke Test Passed Successfully! ---")
