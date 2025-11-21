#!/usr/bin/env python3
"""net_config.py defines the configuration, constants, and master schema for the Network module"""

import re
from enum import Enum
from typing import Dict, Any, List

from BachiCoin.lib_crossmodule.crossmodule_config import NetworkType

NET_INDEX_KEY = "net_index"

NET_SCHEMA_VERSION: int = 0

# JIT (Just-In-Time) fields - populated during processing, not in static defaults
JIT_FIELDS: List[str] = [
    "node_id",
    "created_at",
    "last_seen",
]

# --- Enums for Controlled Vocabularies ---

class NodeStatus(Enum):
    """Defines the lifecycle status of a network node."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SYNCHING = "synching"
    OFFLINE = "offline"
    JAILED = "jailed"

class NodeType(Enum):
    """Defines the role of a network node."""
    FULL_NODE = "full_node"
    LIGHT_NODE = "light_node"
    ARCHIVAL_NODE = "archival_node"
    VALIDATOR = "validator"
    BOOTSTRAP = "bootstrap"

class NetConfig:
    """A pure configuration class defining the node schema, constraints, and defaults."""
    # --- Constants and Business Rules ---
    NODE_ID_PATTERN = re.compile(r'^N_[a-fA-F0-9]{16}$'
) # Updated for hash-based IDs
    DEFAULT_P2P_PORT = 9333
    DEFAULT_RPC_PORT = 9334
    MAX_PEERS = 50
    DEFAULT_NODE_TYPE = NodeType.FULL_NODE.value # Changed from NodeType.TESTNET.value
    DEFAULT_STATUS = NodeStatus.ACTIVE.value
    PEER_TIMEOUT_SECONDS = 60 # New constant for peer management

    # --- Master Schema Definition ---
    _NODE_MASTER_SCHEMA: Dict[str, Dict[str, Any]] = {
        # Core identification
        "node_id": {"type": str, "required": True, "immutable": True, "format": "node_id"},
        "node_url": {"type": str, "required": True, "unique": True},
        "ip_address": {"type": str, "required": True},
        "p2p_port": {"type": int, "required": True, "default": DEFAULT_P2P_PORT},
        "rpc_port": {"type": int, "required": False, "default": DEFAULT_RPC_PORT},

        # Node classification
        "node_type": {"type": str, "required": True, "default": DEFAULT_NODE_TYPE,
                      "allowed_values": [t.value for t in NodeType]},
        "status": {"type": str, "required": True, "default": DEFAULT_STATUS,
                   "allowed_values": [s.value for s in NodeStatus]},

        # Timestamps
        "created_at": {"type": str, "required": True, "format": "iso8601", "immutable": True},
        "last_seen": {"type": str, "required": True, "format": "iso8601"},

        # Peers (list of peer_ids or simple contact info)
        "peers": {"type": list, "required": False, "default": [], "max_items": MAX_PEERS},

        # System metadata
        "region": {"type": str, "required": False},
        "protocol": {"type": str, "required": False},
        "metadata": {"type": dict, "required": False, "default": {}},
    }

    # --- Schema Views ---
    NODE_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "full_schema": list(_NODE_MASTER_SCHEMA.keys()),
        "create": [
            "node_url", "ip_address", "p2p_port", "rpc_port", "node_type"
        ],
        "index": [
            "node_id", "node_url", "status", "node_type", "last_seen", "region", "protocol"
        ],
    }

    DEFAULT_NETWORK = NetworkType.TESTNET.value

    # --- Node Type Defaults ---
    NODE_TYPE_DEFAULTS = {
        # Removed NodeType.TESTNET.value as it's a NetworkType, not a NodeType
        NodeType.FULL_NODE.value: {
            "max_peers": MAX_PEERS,
        }
    }

    @classmethod
    def get_node_schema_view(cls, view: str) -> Dict[str, Any]:
        """Gets the schema definition for a specific view."""
        assert view in cls.NODE_SCHEMA_VIEWS, f"Unknown node schema view: {view}"
        view_fields = cls.NODE_SCHEMA_VIEWS[view]
        return {k: cls._NODE_MASTER_SCHEMA[k] for k in view_fields if k in cls._NODE_MASTER_SCHEMA}

    @classmethod
    def get_node_defaults(cls) -> Dict[str, Any]:
        """Gets a complete default node object based on the master schema."""
        defaults = {}
        for field, config in cls._NODE_MASTER_SCHEMA.items():
            if field in JIT_FIELDS: # Handle JIT fields
                defaults[field] = None
            elif "default" in config:
                defaults[field] = config["default"]
            else:
                # Assign an appropriate empty value for fields without a default
                field_type = config.get("type", str)
                if field_type == list:
                    defaults[field] = []
                elif field_type == dict:
                    defaults[field] = {}
                else:
                    defaults[field] = None  # Default for str, int, float, bool
        return defaults

    @classmethod
    def get_required_fields(cls, view: str = "full_schema") -> List[str]:
        """Returns the list of required fields for a given schema view."""
        schema = cls.get_node_schema_view(view)
        return [field for field, config in schema.items() if config.get("required")]

    @classmethod
    def get_immutable_fields(cls) -> List[str]:
        """Returns a list of fields that cannot be changed after creation."""
        return [k for k, v in cls._NODE_MASTER_SCHEMA.items() if v.get("immutable")]


if __name__ == "__main__":
    """A simple smoke test to verify that the configuration can be loaded"""

    print("--- Running NetConfig Smoke Test ---")
    print(f"✅ Default P2P Port: {NetConfig.DEFAULT_P2P_PORT}")
    print(f"✅ NodeType Enum 'VALIDATOR': {NodeType.VALIDATOR.value}")
    create_view_fields = NetConfig.get_node_schema_view("create").keys()
    print(f"✅ 'create' view fields: {list(create_view_fields)}")
    defaults = NetConfig.get_node_defaults()
    print(f"✅ Default node config: {defaults}")
    assert defaults["node_id"] is None, "JIT field 'node_id' should be None by default."
    print("✅ JIT field 'node_id' correctly set to None in defaults.")
    print("\n--- NetConfig Smoke Test Passed Successfully! ---")
