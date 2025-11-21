#!/usr/bin/env python3
"""validator_storage_adapter.py - Provides a backend-agnostic storage adapter for user data"""


from typing import Dict, Any, Optional, List
from datetime import datetime

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_validator.validator_config import VALIDATOR_INDEX_KEY


class ValidatorStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== VALIDATOR REGISTRY OPERATIONS ===================

    def save_validator_index(self, index_data: Dict[str, Any]) -> bool:
        """Save the main validator index file."""
        return self.provider.save(VALIDATOR_INDEX_KEY, index_data)

    def load_validator_index(self) -> Dict[str, Any]:
        """Load the main validator index file."""
        # Ensure that if the index doesn't exist, we return a default structure.
        return self.provider.load(VALIDATOR_INDEX_KEY) or {}

    def update_validator_index(self, update_func) -> Optional[Dict[str, Any]]:
        """Update the main validator index using the provider's atomic update."""
        # The provider's update method handles the read-modify-write cycle.
        return self.provider.update(VALIDATOR_INDEX_KEY, update_func)

    def save_validator(self, validator_index: int, validator_data: Dict[str, Any]) -> bool:
        """Save individual validator data"""
        return self.provider.save(f"validator_{validator_index}", validator_data)

    def load_validator(self, validator_index: int) -> Optional[Dict[str, Any]]:
        """Load individual validator data"""
        return self.provider.load(f"validator_{validator_index}")

    def update_validator(self, validator_index: int, update_func) -> Optional[Dict[str, Any]]:
        """Update individual validator data"""
        # Re-implementing read-modify-write to bypass provider's cached read.
        current_data = self.load_validator(validator_index)
        if current_data is None:
            return None  # Cannot update non-existent validator

        updated_data = update_func(current_data)
        if self.save_validator(validator_index, updated_data):
            return updated_data
        return None

    def delete_validator(self, validator_index: int) -> bool:
        """Delete individual validator data"""
        return self.provider.delete(f"validator_{validator_index}")

    def list_validators(self) -> List[int]:
        """Lists all validator IDs in the storage as integers, sorted."""
        return sorted([
            int(key.replace("validator_", ""))
            for key in self.provider.list_keys()
            if key.startswith("validator_") and key != VALIDATOR_INDEX_KEY
        ])

    # =================== VALIDATOR PERFORMANCE TRACKING ===================

    def save_validator_performance(self, validator_index: int, performance_data: Dict[str, Any]) -> bool:
        """Save validator performance metrics"""
        return self.provider.save(f"performance_{validator_index}", {
            "validator_index": validator_index,
            "performance": performance_data,
            "recorded_at": self._get_current_timestamp()
        })

    def load_validator_performance(self, validator_index: int) -> Optional[Dict[str, Any]]:
        """Load validator performance metrics"""
        data = self.provider.load(f"performance_{validator_index}")
        return data.get("performance", {}) if data else None

    def update_validator_performance(self, validator_index: int, update_func) -> Optional[Dict[str, Any]]:
        """Update validator performance metrics"""
        return self.provider.update(f"performance_{validator_index}", update_func)

    # =================== VALIDATOR SLASHING OPERATIONS ===================

    def save_slashing_event(self, slashing_id: str, slashing_data: Dict[str, Any]) -> bool:
        """Save slashing event"""
        return self.provider.save(f"slashing_{slashing_id}", slashing_data)

    def load_slashing_event(self, slashing_id: str) -> Optional[Dict[str, Any]]:
        """Load slashing event"""
        return self.provider.load(f"slashing_{slashing_id}")

    def list_slashing_events(self) -> List[Dict[str, Any]]:
        """List all slashing events"""
        slashing_keys = [k for k in self.provider.list_keys() if k.startswith("slashing_")]
        events = []

        for key in slashing_keys:
            event = self.provider.load(key)
            if event:
                event["slashing_id"] = key.replace("slashing_", "")
                events.append(event)

        return events

    def list_slashed_validators(self) -> List[int]:
        """List all slashed validator indices"""
        slashing_events = self.list_slashing_events()
        slashed_validators = []

        for event in slashing_events:
            validator_index = event.get("validator_index")
            if validator_index is not None:
                slashed_validators.append(validator_index)

        return sorted(list(set(slashed_validators)))

    # =================== VALIDATOR ANALYTICS ===================

    def save_validator_metrics(self, epoch: int, metrics: Dict[str, Any]) -> bool:
        """Save validator metrics for epoch"""
        return self.provider.save(f"metrics_{epoch}", {
            "epoch": epoch,
            "metrics": metrics,
            "recorded_at": self._get_current_timestamp()
        })

    def load_validator_metrics(self, epoch: int) -> Optional[Dict[str, Any]]:
        """Load validator metrics for epoch"""
        data = self.provider.load(f"metrics_{epoch}")
        return data.get("metrics", {}) if data else None

    def get_validator_summary(self) -> Dict[str, Any]:
        """Get comprehensive validator storage summary"""
        all_keys = self.provider.list_keys()

        summary = {
            "total_states": len(all_keys),
            "by_type": {
                "validators": 0,
                "performance": 0,
                "slashings": 0,
                "metrics": 0,
                "other": 0
            },
            "validator_count": 0,
            "slashed_count": 0,
            "storage_keys": len(all_keys)
        }

        for key in all_keys:
            if key.startswith("validator_") and key != VALIDATOR_INDEX_KEY:
                summary["by_type"]["validators"] += 1
                summary["validator_count"] += 1
            elif key.startswith("performance_"):
                summary["by_type"]["performance"] += 1
            elif key.startswith("slashing_"):
                summary["by_type"]["slashings"] += 1
                summary["slashed_count"] += 1
            elif key.startswith("metrics_"):
                summary["by_type"]["metrics"] += 1
            elif key == VALIDATOR_INDEX_KEY:
                pass  # Don't count registry as separate validator
            else:
                summary["by_type"]["other"] += 1

        return summary

    # =================== BATCH OPERATIONS ===================

    def batch_update_validators(self, validator_updates: Dict[int, Dict[str, Any]]) -> Dict[int, bool]:
        """Batch update multiple validators"""
        results = {}

        for validator_index, update_data in validator_updates.items():
            def update_func(validator_data):
                validator_data.update(update_data)
                validator_data["last_modified"] = self._get_current_timestamp()
                return validator_data

            result = self.update_validator(validator_index, update_func)
            results[validator_index] = result is not None

        return results

    def batch_save_performance(self, performance_map: Dict[int, Dict[str, Any]]) -> Dict[int, bool]:
        """Batch save performance data for multiple validators"""
        results = {}

        for validator_index, performance_data in performance_map.items():
            success = self.save_validator_performance(validator_index, performance_data)
            results[validator_index] = success

        return results

    # =================== VALIDATOR STATE QUERIES ===================

    def get_active_validator_indices(self) -> List[int]:
        """Get indices of active validators (not slashed/exited)"""
        validator_indices = self.list_validators()
        slashed_validators = set(self.list_slashed_validators())

        active_validators = []
        for validator_index in validator_indices:
            if validator_index not in slashed_validators:
                validator_data = self.load_validator(validator_index)
                if validator_data and validator_data.get("status") == "active_ongoing":
                    active_validators.append(validator_index)

        return sorted(active_validators)

    def get_validator_count_by_status(self) -> Dict[str, int]:
        """Get count of validators by status"""
        validator_indices = self.list_validators()
        status_counts = {}

        for validator_index in validator_indices:
            validator_data = self.load_validator(validator_index)
            if validator_data:
                status = validator_data.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

        return status_counts

    def get_total_effective_balance(self) -> int:
        """Get total effective balance of all validators"""
        validator_indices = self.list_validators()
        total_balance = 0

        for validator_index in validator_indices:
            validator_data = self.load_validator(validator_index)
            if validator_data:
                total_balance += validator_data.get("effective_balance", 0)

        return total_balance

    # =================== PRIVATE HELPER METHODS ===================

    def _get_current_timestamp(self) -> str:
        """Get current ISO timestamp"""
        return datetime.now().isoformat() + "Z"

    def close(self) -> None:
        """Close storage connection"""
        self.provider.close()


if __name__ == "__main__":
    """Unit test for the new, modular validator storage adapter."""
    from BachiCoin.lib_validator.validator_storage_factory import ValidatorStorageFactory
    from tests.test_config import dirs

    print("=== ValidatorStorageAdapter (Modular) Unit Test ===")
    adapter = ValidatorStorageFactory.create_validator_storage(dirs)
    print(f"\n🧪 Testing validator index operations...")
    # Test validator index
    test_index = {
        "validators": {
            "0": {"validator_index": 0, "pubkey": "0x" + "a" * 96, "status": "active_ongoing"}
        },
        "by_pubkey": {"0x" + "a" * 96: 0},
        "by_user": {"U_TEST_123": 0},
        "metadata": {"total_validators": 1}
    }

    index_saved = adapter.save_validator_index(test_index)
    print(f"✅ Save validator index: {index_saved}")

    loaded_index = adapter.load_validator_index()
    print(f"✅ Load validator index: {loaded_index is not None}")
    if loaded_index:
        print(f"   Total validators: {loaded_index.get('metadata', {}).get('total_validators', 'N/A')}")

    print(f"\n🧪 Testing individual validator operations...")

    # Test individual validators
    test_validator_data = {
        "validator_index": 1,
        "pubkey": "0x" + "c" * 96,
        "status": "active_ongoing",
    }

    validator_saved = adapter.save_validator(1, test_validator_data)
    print(f"✅ Save validator 1: {validator_saved}")

    # Test validator listing
    validator_indices = adapter.list_validators()
    print(f"✅ List validators: {validator_indices}")
    assert 1 in validator_indices

    # Test validator loading
    loaded_validator = adapter.load_validator(1)
    print(f"✅ Load validator 1: {loaded_validator is not None}")
    assert loaded_validator and loaded_validator["pubkey"] == "0x" + "c" * 96

    # Test update
    def update_status(data):
        data["status"] = "active_exiting"
        return data
    adapter.update_validator(1, update_status)
    updated_validator = adapter.load_validator(1)
    print(f"✅ Update validator 1 status: {updated_validator.get('status')}")
    assert updated_validator and updated_validator["status"] == "active_exiting"

    # Test deletion
    deleted = adapter.delete_validator(1)
    print(f"✅ Delete validator 1: {deleted}")
    assert adapter.load_validator(1) is None

    # Cleanup
    adapter.close()
    print(f"✅ Adapter closed")

    print("\n✅ ValidatorStorageAdapter (Modular) Test Complete!")