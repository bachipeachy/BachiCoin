#!/usr/bin/env python3
"""Modern mempool network validation - ETH-aligned gossip and peer validation
CLEAN: Network layer validation only, delegates transaction validation to mempool_config
"""

import time
import json
from typing import Dict, Any, List
from datetime import datetime, timezone

from BachiCoin.lib_mempool.mempool_config import MempoolConfig, validate_mempool_transaction
from BachiCoin.lib_transaction.tx_validation import TxConfig, is_valid_tx_hash, is_valid_address

class NetworkValidationError(Exception):
    """Network validation error for gossip layer"""
    pass

class NetworkValidator:
    """Network layer validation for gossip messages and peer interactions"""
    
    # Network-specific constants (ETH standards)
    MAX_GOSSIP_SIZE_BYTES = 1024 * 1024  # 1MB gossip message limit
    MAX_PEER_ID_LENGTH = 64              # Standard libp2p peer ID length
    VALID_MESSAGE_TYPES = ["tx_gossip", "block_announce", "peer_discovery"]
    
    @staticmethod
    def validate_gossip_message(message_data: Dict[str, Any]) -> List[str]:
        """Validate network gossip message structure"""
        errors = []
        
        # Required gossip fields
        required_fields = ["message_type", "payload", "peer_id", "timestamp"]
        for field in required_fields:
            if field not in message_data:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return errors
        
        # Message type validation
        msg_type = message_data["message_type"]
        if msg_type not in NetworkValidator.VALID_MESSAGE_TYPES:
            errors.append(f"Invalid message_type: {msg_type}")
        
        # Peer ID validation (simple length check)
        peer_id = message_data["peer_id"]
        if not isinstance(peer_id, str) or len(peer_id) > NetworkValidator.MAX_PEER_ID_LENGTH:
            errors.append("Invalid peer_id format")
        
        # Timestamp validation (must be recent)
        try:
            timestamp_str = message_data["timestamp"]
            if timestamp_str.endswith("Z"):
                timestamp_str = timestamp_str[:-1] + "+00:00"
            msg_time = datetime.fromisoformat(timestamp_str)
            msg_timestamp = msg_time.timestamp()
            now = time.time()
            
            # Allow 5 minutes drift for network propagation
            if msg_timestamp > now + 300:
                errors.append("Message timestamp too far in future")
            if msg_timestamp < now - 3600:  # 1 hour old max
                errors.append("Message timestamp too old")
        except Exception as e:
            errors.append(f"Invalid timestamp format: {e}")
        
        # Payload structure validation
        payload = message_data["payload"]
        if not isinstance(payload, dict):
            errors.append("Payload must be a dictionary")
        
        # Message size limit
        msg_size = len(json.dumps(message_data).encode('utf-8'))
        if msg_size > NetworkValidator.MAX_GOSSIP_SIZE_BYTES:
            errors.append(f"Message too large: {msg_size} > {NetworkValidator.MAX_GOSSIP_SIZE_BYTES}")
        
        return errors
    
    @staticmethod
    def validate_tx_gossip_payload(payload: Dict[str, Any]) -> List[str]:
        """Validate transaction gossip payload structure"""
        errors = []
        
        # Required fields for tx gossip
        if "transaction" not in payload:
            errors.append("Missing transaction in gossip payload")
            return errors
        
        transaction = payload["transaction"]
        if not isinstance(transaction, dict):
            errors.append("Transaction must be a dictionary")
            return errors
        
        # Basic required fields for network transmission
        network_required_fields = [
            "tx_hash", "from_address", "to_address", "nonce", 
            "max_fee_per_gas", "max_priority_fee_per_gas", "signature"
        ]
        
        for field in network_required_fields:
            if field not in transaction:
                errors.append(f"Missing required transaction field: {field}")
        
        if errors:
            return errors
        
        # Quick format checks using tx_config validation
        if not is_valid_tx_hash(transaction.get("tx_hash", "")):
            errors.append("Invalid tx_hash format")
        
        if not is_valid_address(transaction.get("from_address", "")):
            errors.append("Invalid from_address format")
        
        if not is_valid_address(transaction.get("to_address", "")):
            errors.append("Invalid to_address format")
        
        # Nonce must be non-negative integer
        nonce = transaction.get("nonce")
        if not isinstance(nonce, int) or nonce < 0:
            errors.append("Invalid nonce: must be non-negative integer")
        
        # Gas fees must be positive
        max_fee = transaction.get("max_fee_per_gas", 0)
        priority_fee = transaction.get("max_priority_fee_per_gas", 0)
        
        if not isinstance(max_fee, (int, float)) or max_fee <= 0:
            errors.append("max_fee_per_gas must be positive")
        
        if not isinstance(priority_fee, (int, float)) or priority_fee < 0:
            errors.append("max_priority_fee_per_gas must be non-negative")
        
        # Priority fee cannot exceed max fee
        if priority_fee > max_fee:
            errors.append("max_priority_fee_per_gas cannot exceed max_fee_per_gas")
        
        return errors
    
    @staticmethod
    def validate_network_transaction_full(tx_data: Dict[str, Any], pool_state: Dict[str, Any] = None, account_state: Dict[str, Any] = None) -> List[str]:
        """Complete network transaction validation - delegates to mempool validation"""
        
        # Use default states if not provided
        if pool_state is None:
            pool_state = {"total_size": 0, "account_pending": {}, "memory_usage_bytes": 0}
        
        if account_state is None:
            account_state = {"next_nonce": 0, "pending_nonces": set()}
        
        # Delegate to comprehensive mempool validation
        return validate_mempool_transaction(tx_data, pool_state, account_state)

class NetworkGossipValidator:
    """Specialized validator for different gossip message types"""
    
    @staticmethod
    def validate_tx_gossip(message_data: Dict[str, Any]) -> List[str]:
        """Complete validation for transaction gossip messages"""
        errors = []
        
        # 1. Basic gossip message structure
        errors.extend(NetworkValidator.validate_gossip_message(message_data))
        
        if errors:
            return errors
        
        # 2. TX gossip payload structure
        payload = message_data["payload"]
        errors.extend(NetworkValidator.validate_tx_gossip_payload(payload))
        
        return errors
    
    @staticmethod
    def validate_block_announce(message_data: Dict[str, Any]) -> List[str]:
        """Validate block announcement gossip"""
        errors = []
        
        # Basic message validation
        errors.extend(NetworkValidator.validate_gossip_message(message_data))
        
        if errors:
            return errors
        
        # Block-specific payload validation
        payload = message_data["payload"]
        required_block_fields = ["block_hash", "block_number", "parent_hash", "tx_count"]
        
        for field in required_block_fields:
            if field not in payload:
                errors.append(f"Missing block field: {field}")
        
        # Block hash format
        if "block_hash" in payload and not is_valid_tx_hash(payload["block_hash"]):
            errors.append("Invalid block_hash format")
        
        # Block number must be positive
        block_number = payload.get("block_number")
        if not isinstance(block_number, int) or block_number < 0:
            errors.append("Invalid block_number")
        
        return errors

# Convenience functions for network layer
def validate_network_gossip(message_data: Dict[str, Any]) -> List[str]:
    """Route gossip validation by message type"""
    msg_type = message_data.get("message_type", "")
    
    if msg_type == "tx_gossip":
        return NetworkGossipValidator.validate_tx_gossip(message_data)
    elif msg_type == "block_announce":
        return NetworkGossipValidator.validate_block_announce(message_data)
    else:
        return NetworkValidator.validate_gossip_message(message_data)

def is_valid_network_gossip(message_data: Dict[str, Any]) -> bool:
    """Quick boolean check for gossip message validity"""
    return len(validate_network_gossip(message_data)) == 0

def assert_valid_network_gossip(message_data: Dict[str, Any]) -> None:
    """Fail-fast assertion for gossip validation"""
    errors = validate_network_gossip(message_data)
    assert not errors, f"Network gossip validation failed: {errors}"

def validate_peer_transaction(tx_data: Dict[str, Any]) -> List[str]:
    """Validate transaction received from network peer"""
    # Delegate to comprehensive mempool validation with empty states
    return NetworkValidator.validate_network_transaction_full(tx_data)

def is_valid_peer_transaction(tx_data: Dict[str, Any]) -> bool:
    """Quick boolean check for peer transaction validity"""
    return len(validate_peer_transaction(tx_data)) == 0

def assert_valid_peer_transaction(tx_data: Dict[str, Any]) -> None:
    """Fail-fast assertion for peer transaction validation"""
    errors = validate_peer_transaction(tx_data)
    assert not errors, f"Peer transaction validation failed: {errors}"

# Legacy aliases for broadcaster/listener compatibility
def assert_valid_network_transaction(tx_data: Dict[str, Any]) -> None:
    """Legacy alias for broadcaster/listener compatibility"""
    assert_valid_peer_transaction(tx_data)

def assert_valid_network_message(message_data: Dict[str, Any]) -> None:
    """Legacy alias for broadcaster/listener compatibility"""
    assert_valid_network_gossip(message_data)

if __name__ == "__main__":
    print("=== Modern Network Validation - ETH Standards ===")
    print("• Focuses on network/gossip layer validation")
    print("• Delegates transaction validation to mempool_config")
    print("• EIP-1559 aligned field validation")
    print("• No backward compatibility")
    
    # Test transaction gossip message
    sample_tx = {
        "tx_hash": "0x" + "a" * 64,
        "from_address": "0x" + "1" * 40,
        "to_address": "0x" + "2" * 40,
        "nonce": 1,
        "max_fee_per_gas": 40.0,
        "max_priority_fee_per_gas": 2.0,
        "gas_limit": 21000,
        "signature": "0x" + "a" * 130
    }
    
    gossip_message = {
        "message_type": "tx_gossip",
        "payload": {"transaction": sample_tx},
        "peer_id": "peer123",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Test gossip validation
    gossip_errors = validate_network_gossip(gossip_message)
    print(f"\n✅ Gossip validation: {len(gossip_errors)} errors")
    if gossip_errors:
        print(f"   Errors: {gossip_errors}")
    
    # Test transaction validation (delegates to mempool_config)
    tx_errors = validate_peer_transaction(sample_tx)
    print(f"✅ Transaction validation: {len(tx_errors)} errors")
    if tx_errors:
        print(f"   Errors: {tx_errors}")
    
    # Test block announcement
    block_announce = {
        "message_type": "block_announce",
        "payload": {
            "block_hash": "0x" + "b" * 64,
            "block_number": 12345,
            "parent_hash": "0x" + "c" * 64,
            "tx_count": 150
        },
        "peer_id": "peer456",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    block_errors = validate_network_gossip(block_announce)
    print(f"✅ Block announce validation: {len(block_errors)} errors")
    
    print(f"\n✅ Network validation ready - focuses on gossip layer!")
    print(f"✅ Uses existing validation from mempool_config.py")
    print(f"✅ ETH-aligned with no legacy support")