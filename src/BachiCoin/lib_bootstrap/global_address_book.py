import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_STORAGE_PATH = "/tmp/bachicoin_testnet_addresses.json"

class GlobalAddressBook:
    """A file-based, flat address book mapping user keys to public addresses."""

    def __init__(self, storage_path: str = DEFAULT_STORAGE_PATH):
        """Initializes the address book, loading from the given storage path."""
        self.storage_path = Path(storage_path)
        self._addresses = self._load()

    def _load(self) -> Dict[str, str]:
        """Loads addresses from the storage file if it exists."""
        if self.storage_path.exists():
            with self.storage_path.open("r") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}
        return {}

    def _save(self):
        """Saves the current addresses to the storage file."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("w") as f:
            json.dump(self._addresses, f, indent=2)

    def update_global_address_book(self, user_key: str, pub_address: str):
        """Adds or updates a user's public address in the address book."""
        self._addresses[user_key] = pub_address
        self._save()

    def get_pub_address(self, user_key: str) -> Optional[str]:
        """Retrieves the public address for a given user_key."""
        return self._addresses.get(user_key)

    def get_all_addresses(self) -> Dict[str, str]:
        """Returns a dictionary of all registered user keys and their addresses."""
        return self._addresses

    def clear(self):
        """Clears all entries from the address book."""
        self._addresses = {}
        self._save()

if __name__ == "__main__":
    import os

    # Smoke test
    storage_path = "/tmp/bachicoin_test_address_book.json"
    if os.path.exists(storage_path):
        os.remove(storage_path)
        
    address_book = GlobalAddressBook(storage_path=storage_path)

    # 1. Clear should create an empty file
    address_book.clear()
    assert os.path.exists(storage_path)
    assert address_book.get_all_addresses() == {}

    # 2. Add a user address
    address_book.update_global_address_book("Gomer_Adams_private", "0x12345")
    assert address_book.get_pub_address("Gomer_Adams_private") == "0x12345"

    # 3. Add another user address
    address_book.update_global_address_book("Isha_Adams_business", "0x67890")
    assert len(address_book.get_all_addresses()) == 2

    # 4. Verify persistence by creating a new instance
    new_address_book = GlobalAddressBook(storage_path=storage_path)
    assert new_address_book.get_pub_address("Isha_Adams_business") == "0x67890"
    
    # 5. Clean up
    os.remove(storage_path)
    assert not os.path.exists(storage_path)

    print("GlobalAddressBook smoke test passed!")
