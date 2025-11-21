#!/usr/bin/env python3
"""attestor_storage_adapter.py - Provides a backend-agnostic storage adapter for user data"""

from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_attestor.attestor_config import ATTESTOR_INDEX_KEY


class AttestorStorageAdapter:
    """Adapter for attestation-related storage operations."""

    def __init__(self, provider: StorageProvider):
        """Initializes the adapter with a storage provider."""
        self.provider = provider

    # =================== ATTESTOR INDEX OPERATIONS ===================

    def save_attestor_index(self, index_data: Dict[str, Any]) -> bool:
        """Saves the main attestor index."""
        return self.provider.save(ATTESTOR_INDEX_KEY, index_data)

    def load_attestor_index(self) -> Dict[str, Any]:
        """Loads the main attestor index, returning an empty dict if not found."""
        return self.provider.load(ATTESTOR_INDEX_KEY) or {}

    def update_attestor_index(self, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates the main attestor index."""
        return self.provider.update(ATTESTOR_INDEX_KEY, update_func)

    # =================== INDIVIDUAL ATTESTATION OPERATIONS ===================

    def save_attestation(self, attestation_id: str, attestation_data: Dict[str, Any]) -> bool:
        """Saves an individual attestation record, keyed by its unique ID."""
        return self.provider.save(f"attestation_{attestation_id}", attestation_data)

    def load_attestation(self, attestation_id: str) -> Optional[Dict[str, Any]]:
        """Loads an individual attestation record by its ID."""
        return self.provider.load(f"attestation_{attestation_id}")

    def update_attestation(self, attestation_id: str, update_func: Callable) -> Optional[Dict[str, Any]]:
        """Atomically updates an individual attestation record."""
        return self.provider.update(f"attestation_{attestation_id}", update_func)

    def delete_attestation(self, attestation_id: str) -> bool:
        """Deletes an individual attestation record by its ID."""
        return self.provider.delete(f"attestation_{attestation_id}")

    def list_attestation_ids(self) -> List[str]:
        """Lists all attestation IDs based on stored attestation files."""
        return sorted([
            key.replace("attestation_", "")
            for key in self.provider.list_keys()
            if key.startswith("attestation_")
        ])

    def close(self) -> None:
        """Closes the underlying storage provider connection."""
        self.provider.close()


if __name__ == "__main__":
    """A simple smoke test for the AttestorStorageAdapter."""
    import tempfile
    import shutil
    from pathlib import Path

    from BachiCoin.lib_attestor.attestor_storage_factory import AttestorStorageFactory
    from tests.test_config import dirs

    print("=== AttestorStorageAdapter + Factory Smoke Test ===")

    # 1. Create adapter via the factory
    adapter = AttestorStorageFactory.create_attestor_storage(dirs)
    print(f"{adapter}\nstores data at {dirs.attestor}")

    # 2. Test index operations
    test_index = {"metadata": {"total_attestations": 0}, "duties": {}}
    assert adapter.save_attestor_index(test_index), "Failed to save index"
    loaded_index = adapter.load_attestor_index()
    assert loaded_index == test_index, "Loaded index does not match saved index"
    print("✅ Index operations successful.")

    # 3. Verify the physical index file was created correctly
    expected_file = Path(dirs.attestor) / f"{ATTESTOR_INDEX_KEY}.json"
    assert expected_file.exists(), f"Expected index file {expected_file} was not created."
    print(f"✅ Index file correctly created at: {expected_file}")

    # 4. Test individual attestation operations
    attestation_id = "10-123"
    attestation_data = {"attestation_id": attestation_id, "status": "awaiting_duty"}
    assert adapter.save_attestation(attestation_id, attestation_data), "Failed to save attestation"
    loaded_attestation = adapter.load_attestation(attestation_id)
    assert loaded_attestation == attestation_data, "Loaded attestation does not match"
    assert adapter.list_attestation_ids() == [attestation_id], "Attestation ID not found in list"
    print("✅ Individual attestation operations successful.")

    adapter.close()
    print("✅ Adapter closed successfully.")


    print("\n--- Smoke Test Passed Successfully! ---")
