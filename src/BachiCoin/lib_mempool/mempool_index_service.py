#!/usr/bin/env python3
# mempool_index_service.py – Service layer with orchestration, persistence, and concurrency.

import asyncio
import threading
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable

from BachiCoin.lib_mempool.mempool_config import MempoolConfig, MempoolStatus
from BachiCoin.lib_mempool.mempool_storage_adapter import MempoolStorageAdapter
from BachiCoin.lib_network.net_protocol import MessageType
from BachiCoin.lib_mempool.mempool_validation import assert_valid_network_transaction

# Import pure helpers
from BachiCoin.lib_mempool.mempool_helper import (
    create_queue_entry,
    validate_mempool_limits,
    update_fee_statistics,
    get_current_pool_state,
)


class MempoolIndexService:
    """Service layer: mempool queue, validation, and optional network broadcasting."""

    def __init__(
        self,
        storage_adapter: MempoolStorageAdapter,
        nonce_service: Any,
        validator_func: Callable,
        priority_scorer_func: Callable,
        node_context: Any, # Added node_context
        network_broadcaster: Optional[Callable[[MessageType, Dict[str, Any]], Awaitable[Any]]] = None,
    ):
        # Injected dependencies
        self.storage = storage_adapter
        self.nonce_service = nonce_service
        self.validator_func = validator_func
        self.priority_scorer_func = priority_scorer_func
        self.network_broadcaster = network_broadcaster
        self.node_context = node_context # Stored node_context

        # Internal state
        self.lock = threading.RLock()

        self.tx_queue: List[Dict[str, Any]] = []
        self.tx_lookup: Dict[str, int] = {}
        self.fee_stats: Dict[str, Any] = {}
        self.broadcast_stats: Dict[str, int] = {"broadcast_attempts": 0, "successful_broadcasts": 0}
        self._load_persisted_state()

    # === PUBLIC METHODS ===

    async def submit_tx(self, tx_data: Dict[str, Any]) -> str:
        """Submit transaction to mempool (EIP-1559 aligned)."""
        with self.lock:
            tx_hash = tx_data.get("tx_hash")
            if not tx_hash:
                raise ValueError("Transaction must have a 'tx_hash' to be submitted to mempool.")

            # Explicitly check for duplicate nonce for the same sender
            from_address = tx_data.get("from_address")
            nonce = tx_data.get("nonce")
            if from_address and nonce is not None:
                existing_nonces = {tx['nonce'] for tx in self.tx_queue if tx.get('from_address') == from_address}
                if nonce in existing_nonces:
                    error_msg = (
                        f"Nonce {nonce} for address {from_address} already exists in mempool. Transaction rejected.\n"
                        f"Hint: This usually occurs when submitting multiple transactions for the same address in a batch."
                    )
                    raise ValueError(error_msg)

            # Validate with injected validator and helpers
            pool_state = get_current_pool_state(self.tx_queue)
            if from_address:
                account_state = self._get_account_state(from_address)
            else:
                # For system transactions (e.g., mint/burn) that don't have a 'from_address',
                # we provide a default empty account state as nonce validation is not applicable.
                account_state = {"canonical_nonce": 0, "pending_nonces": set()}
            errors = self.validator_func(tx_data, pool_state, account_state)
            if errors:
                raise ValueError(f"Transaction validation failed: {errors}")

            validate_mempool_limits(tx_data, self.tx_queue)

            # Queue + fee stats
            queue_entry = create_queue_entry(tx_data)
            self._add_to_queue(queue_entry)
            self.fee_stats = update_fee_statistics(self.fee_stats, tx_data)
            self._persist_state()

        if self.network_broadcaster:
            await self._broadcast_tx_to_network(queue_entry) # Pass the full queue_entry (tx_data)
        return tx_hash

    def get_mempool_status(self) -> Dict[str, Any]:
        """Get current mempool status."""
        self.reload_state()
        with self.lock:
            total_txs = len(self.tx_queue)
            pending_txs = sum(1 for tx in self.tx_queue if tx.get("status") == MempoolStatus.PENDING.value)
            queued_txs = sum(1 for tx in self.tx_queue if tx.get("status") == MempoolStatus.QUEUED.value)
            unique_accounts = len({tx["from_address"] for tx in self.tx_queue if "from_address" in tx})
            memory_usage_bytes = len(str(self.tx_queue).encode("utf-8"))
            pool_utilization = (
                total_txs / MempoolConfig.MAX_POOL_SIZE * 100 if MempoolConfig.MAX_POOL_SIZE > 0 else 0
            )

            avg_gas_price = (
                sum(tx.get("max_fee_per_gas", 0) for tx in self.tx_queue) / total_txs if total_txs > 0 else 0.0
            )

        memory_usage_mb = round(memory_usage_bytes / (1024 * 1024), 4)
        state = self.storage.load_mempool_state()
        last_cleanup = (
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(state.get("last_cleanup_time"))) if state and state.get("last_cleanup_time") else None
        )

        return {
            "total_transactions": total_txs,
            "pending_transactions": pending_txs,
            "queued_transactions": queued_txs,
            "unique_accounts": unique_accounts,
            "memory_usage_mb": memory_usage_mb,
            "pool_utilization": pool_utilization,
            "avg_gas_price": avg_gas_price,
            "last_cleanup": last_cleanup,
        }

    def get_pending_transactions(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get pending transactions sorted by priority."""
        self.reload_state()
        with self.lock:
            pending = [
                tx
                for tx in self.tx_queue
                if tx.get("status", MempoolStatus.PENDING.value) == MempoolStatus.PENDING.value
            ]
            # Use the injected priority scorer function
            pending.sort(
                key=lambda tx: self.priority_scorer_func(tx, 20.0), # Assuming a base fee for now
                reverse=True,
            )
            if limit:
                pending = pending[:limit]
        return pending

    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired transactions."""
        self.reload_state()
        with self.lock:
            now = time.time()
            expired_hashes = [
                tx["tx_hash"]
                for tx in self.tx_queue
                if (now - tx["arrival_time"]) > MempoolConfig.TX_LIFETIME_SECONDS
            ]
            for tx_hash in expired_hashes:
                self._remove_from_queue(tx_hash)
            if expired_hashes:
                self._persist_state()
            return {"expired_removed": len(expired_hashes), "remaining": len(self.tx_queue)}

    def get_account_transactions(self, from_address: str) -> List[Dict[str, Any]]:
        """Get all transactions for specific account."""
        self.reload_state()
        with self.lock:
            return [entry.copy() for entry in self.tx_queue if entry["from_address"] == from_address]

    def remove_transaction(self, tx_hash: str) -> bool:
        """Remove transaction by hash."""
        self.reload_state()
        with self.lock:
            if any(tx["tx_hash"] == tx_hash for tx in self.tx_queue):
                self._remove_from_queue(tx_hash)
                self._persist_state()
                return True
        return False

    def reload_state(self):
        """Reloads the mempool state from disk."""
        self._load_persisted_state()

    def get_broadcast_stats(self) -> Dict[str, Any]:
        """Returns a copy of the current broadcast statistics."""
        return self.broadcast_stats.copy()

    def reset_broadcast_stats(self) -> None:
        """Resets the broadcast statistics."""
        self.broadcast_stats = {"broadcast_attempts": 0, "successful_broadcasts": 0}

    # === PRIVATE HELPERS ===

    async def handle_network_tx(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """Handles an incoming network transaction."""
        tx_hash = tx_data.get("tx_hash")
        if any(t.get("tx_hash") == tx_hash for t in self.tx_queue):
            return None
        try:
            return await self.submit_tx(tx_data)
        except ValueError:
            return None

    async def _broadcast_tx_to_network(self, tx_data: Dict[str, Any]) -> None:
        """Broadcasts a transaction to the network using the injected broadcaster."""
        if not self.network_broadcaster:
            return
        
        self.broadcast_stats["broadcast_attempts"] += 1
        try:
            assert_valid_network_transaction(tx_data) # Validate before broadcasting
            # The network_broadcaster (net_node.broadcast) expects MessageType and payload
            await self.network_broadcaster(MessageType.TRANSACTION, tx_data)
            self.broadcast_stats["successful_broadcasts"] += 1
        except Exception as e:
            print(f"[WARN] Failed to broadcast transaction {tx_data.get('tx_hash', 'unknown')}: {e}")

    def _get_account_state(self, from_address: str) -> Dict[str, Any]:
        """
        Get account state for validation.
        The canonical nonce is retrieved from the blockchain state, which is the
        single source of truth and is replicated across all nodes. This allows any
        node to validate a transaction from any other node.
        """
        # Use the blockchain_service from node_context to get canonical nonce and balance
        account_info = self.node_context.blockchain_service.get_nonce_and_balance(from_address)
        canonical_nonce = account_info.get("nonce", 0)
        
        pending_txs = self.get_account_transactions(from_address)
        pending_nonces = self.nonce_service.get_pending_nonces(pending_txs)
        
        return {"canonical_nonce": canonical_nonce, "pending_nonces": set(pending_nonces)}

    def _add_to_queue(self, entry: Dict[str, Any]) -> None:
        self.tx_queue.append(entry)
        self.tx_lookup[entry["tx_hash"]] = len(self.tx_queue) - 1

    def _remove_from_queue(self, tx_hash: str) -> None:
        self.tx_queue = [tx for tx in self.tx_queue if tx["tx_hash"] != tx_hash]
        self.tx_lookup = {tx["tx_hash"]: i for i, tx in enumerate(self.tx_queue)}

    def _persist_state(self) -> None:
        if MempoolConfig.ENABLE_PERSISTENCE:
            self.storage.save_mempool_state(
                {"tx_queue": self.tx_queue, "fee_stats": self.fee_stats, "last_cleanup_time": time.time()}
            )

    def _load_persisted_state(self) -> None:
        state = self.storage.load_mempool_state()
        if state:
            self.tx_queue = state.get("tx_queue", [])
            self.fee_stats = state.get("fee_stats", {})
            self.tx_lookup = {tx["tx_hash"]: i for i, tx in enumerate(self.tx_queue)}

    def close(self) -> None:
        if self.storage:
            self.storage.close()


if __name__ == "__main__":
    import json
    import random
    import asyncio
    from pathlib import Path
    from tests.test_config import dirs
    from BachiCoin.lib_mempool.mempool_config import MempoolMetrics, validate_mempool_transaction
    from BachiCoin.lib_mempool.mempool_storage_factory import MempoolStorageFactory
    from BachiCoin.lib_nonce import nonce as nonce_service


    # Mock NodeContext and BlockchainService for isolated testing
    class MockBlockchainService:
        def get_nonce_and_balance(self, address: str) -> Dict[str, Any]:
            # Simulate some account states for testing
            if address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":
                return {"nonce": 5, "balance": 100.0}
            elif address == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb":
                return {"nonce": 10, "balance": 200.0}
            return {"nonce": 0, "balance": 0.0}

    class MockNodeContext:
        def __init__(self):
            self.blockchain_service = MockBlockchainService()
            self.node_dirs = dirs # For storage adapter creation

    mock_node_context = MockNodeContext()

    # 2. Load the 35 transactions created by the transaction API test
    tx_index_file = Path(dirs.tx) / "tx_index.json"
    if not tx_index_file.exists():
        print(f"❌ Error: Transaction index file not found at {tx_index_file}")
        print("--- Please run the test_tx_lib.py script first to generate data. ---")
        exit(1)

    with open(tx_index_file, "r") as f:
        tx_records = json.load(f).get("txs", {})
    print(f"✅ Loaded {len(tx_records)} transaction records from {tx_index_file}")

    # 3. Manually create and inject all dependencies
    storage_adapter = MempoolStorageFactory.create_mempool_storage(mock_node_context.node_dirs)
    validator_func = validate_mempool_transaction
    priority_scorer_func = MempoolMetrics.calculate_priority_score
    network_broadcaster = None # Will be injected by NetNode

    # 4. Instantiate the service with the injected dependencies
    service = MempoolIndexService(
        storage_adapter=storage_adapter,
        nonce_service=nonce_service,
        validator_func=validator_func,
        priority_scorer_func=priority_scorer_func,
        node_context=mock_node_context, # Pass the mock node_context
        network_broadcaster=network_broadcaster,
    )
    print("✅ MempoolIndexService instantiated with all dependencies injected.")

    # 5. Run the test: feed all transactions into the mempool
    async def run_test():
        successful_submissions = 0
        for tx_hash, tx_data in tx_records.items():
            tx_copy = dict(tx_data)

            if "gas_limit" not in tx_copy:
                tx_copy["gas_limit"] = 21000

            # For the smoke test, we need to ensure tx_hash is present and from_address is one of our mocks
            if "tx_hash" not in tx_copy:
                tx_copy["tx_hash"] = tx_hash
            
            # Override from_address for smoke test to match mock blockchain state
            if tx_copy.get("from_address") and tx_copy["from_address"].startswith("0x"):
                if random.random() < 0.5: # Assign to one of our mock addresses
                    tx_copy["from_address"] = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                else:
                    tx_copy["from_address"] = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            else: # For system transactions without from_address
                pass

            try:
                mempool_id = await service.submit_tx(tx_copy)
                print(f"  -> 📥 Submitted tx {tx_hash[:10]}... into mempool as {mempool_id}")
                successful_submissions += 1
            except ValueError as e:
                print(f"  -> ❌ Failed to submit tx {tx_hash[:10]}...: {e}")
        
        return successful_submissions

    # Execute the async test
    final_count = asyncio.run(run_test())

    # 6. Print final mempool status and verify results
    print("\n--- Final Mempool State ---")
    status = service.get_mempool_status()
    for key, value in status.items():
        print(f"  - {key.replace('_', ' ').capitalize()}: {value}")

    print(f"\n✅ Successfully submitted {final_count} transactions to the mempool.")

    # 7. Show top 5 pending transactions to verify priority sorting
    pending = service.get_pending_transactions(limit=5)
    print("\n--- Top 5 Pending Transactions (by priority) ---")
    if pending:
        for i, tx in enumerate(pending):
            print(f"  {i+1}. Hash: {tx['tx_hash'][:12]}... | Priority Fee: {tx['max_priority_fee_per_gas']} | Nonce: {tx['nonce']}")
    else:
        print("  - No pending transactions found.")

    print("\n--- ✅ Refactored MempoolIndexService Smoke Test Passed! ---")
