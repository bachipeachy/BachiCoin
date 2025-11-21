#!/usr/bin/env python3
"""proposer_storage_adapter.py - Provides a backend-agnostic storage adapter for proposer data"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_proposer.proposer_config import PROPOSER_INDEX_KEY


class ProposerStorageAdapter:
    """delegates all I/O operations to a pluggable storage provider"""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a specific storage provider."""
        self.provider = provider

    # =================== PROPOSER INDEX OPERATIONS ===================

    def save_proposer_index(self, index_data: Dict[str, Any]) -> bool:
        """Saves the main proposer index."""
        return self.provider.save(PROPOSER_INDEX_KEY, index_data)

    def load_proposer_index(self) -> Dict[str, Any]:
        """Loads the main proposer index, returning an empty dict if not found."""
        return self.provider.load(PROPOSER_INDEX_KEY) or {}

    def update_proposer_index(self, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates the main proposer index."""
        return self.provider.update(PROPOSER_INDEX_KEY, update_func)

    # =================== INDIVIDUAL PROPOSAL OPERATIONS ===================

    def save_proposal(self, proposal_id: str, proposal_data: Dict[str, Any]) -> bool:
        """Saves an individual proposal record, keyed by its unique ID."""
        return self.provider.save(f"proposal_{proposal_id}", proposal_data)

    def load_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Loads an individual proposal record by its ID."""
        return self.provider.load(f"proposal_{proposal_id}")

    def update_proposal(self, proposal_id: str, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates an individual proposal record."""
        return self.provider.update(f"proposal_{proposal_id}", update_func)

    def delete_proposal(self, proposal_id: str) -> bool:
        """Deletes an individual proposal record by its ID."""
        return self.provider.delete(f"proposal_{proposal_id}")

    def list_proposal_ids(self) -> List[str]:
        """Lists all proposal IDs based on stored proposal files."""
        return sorted([
            key.replace("proposal_", "")
            for key in self.provider.list_keys()
            if key.startswith("proposal_")
        ])

    def close(self) -> None:
        """Closes the underlying storage provider connection."""
        self.provider.close()


if __name__ == "__main__":
    """Unit test for the ProposerStorageAdapter."""
    from BachiCoin.lib_proposer.proposer_storage_factory import ProposerStorageFactory
    from tests.test_config import dirs

    print("=== ProposerStorageAdapter Unit Test ===")

    # 1. Create adapter via the factory
    print("\n🧪 1. Creating adapter...")
    adapter = ProposerStorageFactory.create_proposer_storage(dirs)
    print(f"{adapter}\nstores data in {dirs.proposer}")

    # 2. Test index operations
    print("\n🧪 2. Testing index operations...")
    # Updated to reflect the modern, correct data structure
    test_index = {
        "proposers": {
            "duties_by_slot": {},
            "duties_by_epoch": {},
            "metadata": {"total_duties_assigned": 0}
        }
    }
    assert adapter.save_proposer_index(test_index), "Failed to save index"
    loaded_index = adapter.load_proposer_index()
    assert loaded_index == test_index, "Loaded index does not match saved index"
    print("✅ Index operations successful.")

    # 3. Test individual proposal operations
    print("\n🧪 3. Testing individual proposal operations...")
    proposal_id = "10-320"
    proposal_data = {"proposal_id": proposal_id, "status": "awaiting_duty"}
    assert adapter.save_proposal(proposal_id, proposal_data), "Failed to save proposal"
    loaded_proposal = adapter.load_proposal(proposal_id)
    assert loaded_proposal == proposal_data, "Loaded proposal does not match"
    assert adapter.list_proposal_ids() == [proposal_id], "Proposal ID not found in list"
    print("✅ Individual proposal operations successful.")

    adapter.close()
    print("\n✅ ProposerStorageAdapter Test Complete!")