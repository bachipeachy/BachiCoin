#!/usr/bin/env python3
# mempool_listener.py - ETH 2.0 transaction listening (event-driven, fail fast)

import time
from typing import Dict, Any, Set, Optional, Callable, List

from BachiCoin.lib_mempool.mempool_validation import assert_valid_network_transaction, assert_valid_network_message


# The listener itself does not need to manage the network, so the direct dependency is removed.


class ListenerError(Exception):
    """Listening failed - fail fast"""
    pass


class MempoolListener:
    """ETH 2.0-aligned transaction listener (event-driven). This class is a pure handler."""

    def __init__(self):
        """Initializes the listener state."""
        self.seen_transactions: Set[str] = set()  # Deduplication
        self.transaction_handler: Optional[Callable] = None  # Event handler
        self.listener_stats = {
            "total_received": 0,
            "valid_transactions": 0,
            "duplicate_transactions": 0,
            "invalid_transactions": 0,
            "last_received_time": None
        }

    def register_transaction_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register handler for valid incoming transactions (event-driven)
        Handler receives: transaction data dictionary
        """
        self.transaction_handler = handler

    def handle_incoming_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Handle incoming network message (ETH 2.0 gossip receive)
        Returns: True if message processed successfully
        """
        # Validate network message structure (fail fast)
        assert_valid_network_message(message_data)

        # Extract transaction data
        payload = message_data.get("payload", {}) # Already validated by the call above
        tx_data = payload.get("transaction", {})
        tx_hash = tx_data.get("tx_hash", "")

        # Update stats
        self.listener_stats["total_received"] += 1
        self.listener_stats["last_received_time"] = time.time()

        # Deduplication check
        if self.is_duplicate_transaction(tx_hash):
            self.listener_stats["duplicate_transactions"] += 1
            return False  # Skip duplicates

        # Mark as seen (deduplication)
        self.seen_transactions.add(tx_hash)
        self.listener_stats["valid_transactions"] += 1

        # Emit transaction event
        self.emit_transaction_event(tx_data)

        return True

    def is_duplicate_transaction(self, tx_hash: str) -> bool:
        """Check if transaction already seen (deduplication)"""
        return tx_hash in self.seen_transactions

    def emit_transaction_event(self, tx_data: Dict[str, Any]) -> None:
        """
        Emit transaction event for mempool integration
        Calls registered handler if available
        """
        if self.transaction_handler:
            self.transaction_handler(tx_data)

    def cleanup_seen_transactions(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up old transaction hashes (memory management)
        Returns: Number of hashes cleaned
        """
        # Simple cleanup - clear all for now (KISS)
        # TODO: Implement time-based cleanup when needed
        initial_count = len(self.seen_transactions)
        if initial_count > 10000:  # Prevent memory bloat
            self.seen_transactions.clear()
            return initial_count
        return 0

    def process_transaction_batch(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Process batch of transaction messages (efficiency)
        Returns: Processing statistics
        """
        results = {
            "processed": 0,
            "valid": 0,
            "duplicates": 0,
            "invalid": 0
        }

        for message in messages:
            results["processed"] += 1

            try:
                success = self.handle_incoming_message(message)
                if success:
                    results["valid"] += 1
                else:
                    # Check if it was duplicate or invalid
                    payload = message.get("payload", {})
                    tx_hash = payload.get("tx_data", {}).get("tx_hash", "")
                    if self.is_duplicate_transaction(tx_hash):
                        results["duplicates"] += 1
                    else:
                        results["invalid"] += 1
            except Exception:
                results["invalid"] += 1

        return results

    def get_listener_stats(self) -> Dict[str, Any]:
        """Get listening statistics"""
        stats = self.listener_stats.copy()

        # Calculate processing rates
        total = stats["total_received"]
        if total > 0:
            stats["valid_rate"] = stats["valid_transactions"] / total
            stats["duplicate_rate"] = stats["duplicate_transactions"] / total
            stats["invalid_rate"] = stats["invalid_transactions"] / total
        else:
            stats["valid_rate"] = 0.0
            stats["duplicate_rate"] = 0.0
            stats["invalid_rate"] = 0.0

        # Add memory usage info
        stats["seen_transactions_count"] = len(self.seen_transactions)
        stats["handler_registered"] = self.transaction_handler is not None

        return stats

    def reset_stats(self) -> None:
        """Reset listening statistics"""
        self.listener_stats = {
            "total_received": 0,
            "valid_transactions": 0,
            "duplicate_transactions": 0,
            "invalid_transactions": 0,
            "last_received_time": None
        }

    def clear_seen_transactions(self) -> int:
        """Clear all seen transactions (manual reset)"""
        count = len(self.seen_transactions)
        self.seen_transactions.clear()
        return count

    def get_seen_transaction_count(self) -> int:
        """Get number of seen transactions (deduplication cache size)"""
        return len(self.seen_transactions)

    def is_listening_active(self) -> bool:
        """Check if listener is actively receiving"""
        if not self.listener_stats["last_received_time"]:
            return False

        # Consider active if received message in last 5 minutes
        time_since_last = time.time() - self.listener_stats["last_received_time"]
        return time_since_last < 300

    def close(self) -> None:
        """The listener does not own any resources, so close is a no-op."""
        pass


# Public API functions (event-driven integration)
def create_mempool_listener() -> MempoolListener:
    """Create mempool listener instance"""
    return MempoolListener()


def register_transaction_handler(listener: MempoolListener, handler: Callable[[Dict[str, Any]], None]) -> None:
    """Register transaction event handler"""
    listener.register_transaction_handler(handler)


def handle_network_message(listener: MempoolListener, message_data: Dict[str, Any]) -> bool:
    """Handle incoming network message"""
    return listener.handle_incoming_message(message_data)


if __name__ == "__main__":
    from datetime import datetime, timezone

    print("=== MempoolListener Ready ===")
    print("✅ ETH 2.0 gossip receive pattern")
    print("✅ Event-driven architecture")
    print("✅ Transaction deduplication")
    print("✅ Network validation integration")

    # Standalone test for the handler logic
    listener = create_mempool_listener()


    def my_tx_handler(tx):
        print(f"  -> Handler received transaction: {tx['tx_hash'][:10]}...")


    register_transaction_handler(listener, my_tx_handler)

    valid_message = {
        "message_type": "tx_gossip",
        "peer_id": "test_peer_123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "transaction": {
                "tx_hash": "0x" + "a" * 64,
                "from_address": "0x" + "1" * 40,
                "to_address": "0x" + "2" * 40,
                "signature": "0x" + "s" * 130,
                "nonce": 0,
                "max_fee_per_gas": 40.0,
                "max_priority_fee_per_gas": 2.0
            }
        }
    }

    print("\n🧪 Testing valid message...")
    success = handle_network_message(listener, valid_message)
    print(f"  - Processed successfully: {success}")
    assert success

    print("\n🧪 Testing duplicate message...")
    success_dup = handle_network_message(listener, valid_message)
    print(f"  - Processed successfully: {success_dup}")
    assert not success_dup

    print("\n📊 Final Stats:")
    print(listener.get_listener_stats())
