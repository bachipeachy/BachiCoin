#!/usr/bin/env python3
"""mempool_storage_adapter.py - Provides a backend-agnostic storage adapter for data"""

from typing import Dict, Any, Optional, List, Callable
import time

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_mempool.mempool_config import MEMPOOL_INDEX_KEY


class MempoolStorageAdapter:
    """mempool storage adapter - backend agnostic"""

    def __init__(self, provider: StorageProvider):
        self.provider = provider

    # =================== CORE MEMPOOL STATE OPERATIONS ===================

    def save_mempool_state(self, state_data: Dict[str, Any]) -> bool:
        """Save complete ETH mempool state"""
        return self.provider.save(MEMPOOL_INDEX_KEY, state_data)

    def load_mempool_state(self) -> Optional[Dict[str, Any]]:
        """Load ETH mempool state"""
        return self.provider.load(MEMPOOL_INDEX_KEY)

    def update_mempool_state(self, update_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update mempool state using function"""
        return self.provider.update(MEMPOOL_INDEX_KEY, update_func)

    def clear_mempool(self) -> bool:
        """Clear all mempool data"""
        return self.provider.delete(MEMPOOL_INDEX_KEY)

    def mempool_exists(self) -> bool:
        """Check if mempool state exists"""
        return self.provider.exists(MEMPOOL_INDEX_KEY)

    def list_mempool_keys(self) -> List[str]:
        """List all mempool-related keys"""
        # This method's logic remains as it was, using prefixes if needed.
        return self.provider.list_keys("__mempool")

    # =================== BACKUP AND RESTORE OPERATIONS ===================

    def backup_mempool_state(self, backup_key: str) -> bool:
        """Backup current mempool state"""
        state = self.load_mempool_state()
        if state:
            return self.provider.save(f"__mempool_backup_{backup_key}__", state)
        return False

    def restore_mempool_state(self, backup_key: str) -> bool:
        """Restore mempool state from backup"""
        backup_state = self.provider.load(f"__mempool_backup_{backup_key}__")
        if backup_state:
            return self.save_mempool_state(backup_state)
        return False

    def list_backups(self) -> List[str]:
        """List available backup keys"""
        all_keys = self.provider.list_keys("__mempool_backup_")
        return [key.replace("__mempool_backup_", "").replace("__", "") for key in all_keys]

    def delete_backup(self, backup_key: str) -> bool:
        """Delete a specific backup"""
        return self.provider.delete(f"__mempool_backup_{backup_key}__")

    # =================== ETH-SPECIFIC MEMPOOL OPERATIONS ===================

    def save_transaction_queue(self, queue_data: List[Dict[str, Any]]) -> bool:
        """Save ETH transaction queue separately"""
        return self.provider.save("__eth_tx_queue__", {"queue": queue_data, "saved_at": time.time()})

    def load_transaction_queue(self) -> Optional[List[Dict[str, Any]]]:
        """Load ETH transaction queue"""
        data = self.provider.load("__eth_tx_queue__")
        return data.get("queue", []) if data else None

    def save_account_nonces(self, nonce_data: Dict[str, List[int]]) -> bool:
        """Save ETH account nonce tracking"""
        return self.provider.save("__eth_account_nonces__", {"nonces": nonce_data, "saved_at": time.time()})

    def load_account_nonces(self) -> Optional[Dict[str, List[int]]]:
        """Load ETH account nonce tracking"""
        data = self.provider.load("__eth_account_nonces__")
        return data.get("nonces", {}) if data else None

    def save_fee_statistics(self, fee_stats: Dict[str, Any]) -> bool:
        """Save ETH fee statistics for priority calculation"""
        fee_stats["last_updated"] = time.time()
        return self.provider.save("__eth_fee_stats__", fee_stats)

    def load_fee_statistics(self) -> Optional[Dict[str, Any]]:
        """Load ETH fee statistics"""
        return self.provider.load("__eth_fee_stats__")

    # =================== MONITORING AND ANALYTICS ===================

    def save_queue_snapshot(self, snapshot_data: Dict[str, Any]) -> bool:
        """Save queue snapshot for debugging"""
        snapshot_data["snapshot_time"] = time.time()
        return self.provider.save("__mempool_queue_snapshot__", snapshot_data)

    def load_queue_snapshot(self) -> Optional[Dict[str, Any]]:
        """Load queue snapshot"""
        return self.provider.load("__mempool_queue_snapshot__")

    def save_mempool_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Save mempool metrics/statistics"""
        metrics_data["last_updated"] = time.time()
        return self.provider.save("__mempool_metrics__", metrics_data)

    def load_mempool_metrics(self) -> Optional[Dict[str, Any]]:
        """Load mempool metrics"""
        return self.provider.load("__mempool_metrics__")

    def save_performance_data(self, perf_data: Dict[str, Any]) -> bool:
        """Save ETH mempool performance data"""
        perf_data["recorded_at"] = time.time()
        return self.provider.save("__eth_performance__", perf_data)

    def load_performance_data(self) -> Optional[Dict[str, Any]]:
        """Load ETH mempool performance data"""
        return self.provider.load("__eth_performance__")

    # =================== ETH TRANSACTION TYPE OPERATIONS ===================

    def save_transaction_type_stats(self, type_stats: Dict[str, Any]) -> bool:
        """Save statistics by ETH transaction type (transfer, mint, burn, pool_*)"""
        type_stats["last_updated"] = time.time()
        return self.provider.save("__eth_tx_type_stats__", type_stats)

    def load_transaction_type_stats(self) -> Optional[Dict[str, Any]]:
        """Load statistics by ETH transaction type"""
        return self.provider.load("__eth_tx_type_stats__")

    def save_priority_distribution(self, priority_data: Dict[str, Any]) -> bool:
        """Save ETH priority level distribution data"""
        priority_data["last_updated"] = time.time()
        return self.provider.save("__eth_priority_dist__", priority_data)

    def load_priority_distribution(self) -> Optional[Dict[str, Any]]:
        """Load ETH priority level distribution"""
        return self.provider.load("__eth_priority_dist__")

    # =================== HELPER AND UTILITY OPERATIONS ===================

    def get_mempool_size(self) -> int:
        """Get number of transactions in ETH mempool"""
        state = self.load_mempool_state()
        if state and "tx_queue" in state:
            return len(state["tx_queue"])
        return 0

    def get_account_transaction_count(self, account_address: str) -> int:
        """Get number of pending transactions for ETH account"""
        state = self.load_mempool_state()
        if not state or "tx_queue" not in state:
            return 0

        count = 0
        for tx in state["tx_queue"]:
            if tx.get("from_address") == account_address:
                count += 1
        return count

    def get_mempool_summary(self) -> Dict[str, Any]:
        """Get ETH mempool summary statistics"""
        state = self.load_mempool_state()
        if not state:
            return {"total_transactions": 0, "unique_accounts": 0, "avg_fee": 0.0}

        tx_queue = state.get("tx_queue", [])
        total_transactions = len(tx_queue)

        if total_transactions == 0:
            return {"total_transactions": 0, "unique_accounts": 0, "avg_fee": 0.0}

        unique_accounts = len(set(tx.get("from_address", "") for tx in tx_queue))
        total_fees = sum(tx.get("transaction_fee", 0) for tx in tx_queue)
        avg_fee = total_fees / total_transactions

        return {
            "total_transactions": total_transactions,
            "unique_accounts": unique_accounts,
            "avg_fee": avg_fee,
            "total_fees": total_fees
        }

    # =================== CLEANUP AND MAINTENANCE ===================

    def cleanup_expired_snapshots(self, max_age_seconds: int = 3600) -> int:
        """Clean up old snapshots and temporary data"""
        current_time = time.time()
        cleaned_count = 0

        # Clean up old queue snapshots
        snapshot = self.load_queue_snapshot()
        if snapshot and snapshot.get("snapshot_time", 0) < (current_time - max_age_seconds):
            if self.provider.delete("__mempool_queue_snapshot__"):
                cleaned_count += 1

        return cleaned_count

    def compact_mempool_data(self) -> bool:
        """Compact mempool data by removing unnecessary fields"""
        state = self.load_mempool_state()
        if not state:
            return False

        # Remove any legacy fields or compress data
        compacted = False

        # Remove old schema versions or deprecated fields
        if "deprecated_field" in state:
            del state["deprecated_field"]
            compacted = True

        if compacted:
            return self.save_mempool_state(state)

        return True

    def validate_mempool_integrity(self) -> Dict[str, Any]:
        """Validate ETH mempool data integrity"""
        state = self.load_mempool_state()
        if not state:
            return {"valid": False, "errors": ["No mempool state found"]}

        errors = []
        warnings = []

        # Check required fields
        if "tx_queue" not in state:
            errors.append("Missing tx_queue field")
        if "account_nonces" not in state:
            errors.append("Missing account_nonces field")

        # Validate transaction queue
        tx_queue = state.get("tx_queue", [])
        for i, tx in enumerate(tx_queue):
            if "mempool_id" not in tx:
                errors.append(f"Transaction {i} missing mempool_id")
            if "from_address" not in tx:
                errors.append(f"Transaction {i} missing from_address")
            if "transaction_fee" not in tx:
                errors.append(f"Transaction {i} missing transaction_fee")

        # Check for duplicate mempool IDs
        mempool_ids = [tx.get("mempool_id") for tx in tx_queue if "mempool_id" in tx]
        if len(mempool_ids) != len(set(mempool_ids)):
            errors.append("Duplicate mempool_id values found")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "transaction_count": len(tx_queue),
            "checked_at": time.time()
        }

    def close(self) -> None:
        """Close storage connection"""
        self.provider.close()


if __name__ == "__main__":
    """
    A simple smoke test to verify that the adapter can be initialized"""
    from tests.test_config import dirs

    from BachiCoin.lib_mempool.mempool_storage_factory import MempoolStorageFactory
    print("--- Running MempoolStorageAdapter + Factory Smoke Test ---")

    adapter = MempoolStorageFactory.create_mempool_storage(dirs)
    print(f"✅ {adapter}\nwith storage at {dirs.mempool}")

    assert adapter.mempool_exists(), "Mempool should exist after ensuring it."
    print("✅ ensure_mempool_exists works correctly.")

    initial_state = adapter.load_mempool_state()
    assert initial_state is not None, "load_mempool_state failed on initial state."
    assert initial_state.get("tx_queue") == [], "Initial tx_queue should be empty."
    print("✅ load_mempool_state on initial state is correct.")

    test_state = {"tx_queue": [{"tx_hash": "0x123"}], "account_nonces": {}}
    assert adapter.save_mempool_state(test_state), "save_mempool_state failed."
    loaded_state = adapter.load_mempool_state()
    assert loaded_state == test_state, "Loaded state does not match saved state."
    print("✅ save_mempool_state and load_mempool_state work correctly.")

    assert adapter.clear_mempool(), "clear_mempool failed."
    assert not adapter.mempool_exists(), "Mempool should not exist after clearing."
    print("✅ clear_mempool works correctly.")
    adapter.close()
    print("\n--- Smoke Test Passed Successfully! ---")
