#!/usr/bin/env python3
"""file_provider.py - A file-based storage provider that stores each record as a separate JSON file"""

import threading
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable

from BachiCoin.lib_storage.base_provider import StorageProvider


class FileStorageProvider(StorageProvider[Dict[str, Any]]):
    """The index name is passed in by the consuming factory"""

    def __init__(self, storage_path: str, index_name: str, index_init_data: Optional[Dict[str, Any]] = None):
        """Initializes the file storage."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        # Explicit index file name (no guessing)
        self.index_file = self.storage_path / index_name
        self.index_init_data = index_init_data if index_init_data is not None else {}

        # Ensure index file exists with initial data
        self._ensure_index_exists()

    def _ensure_index_exists(self):
        """Creates the index file if it doesn't exist."""
        with self._lock:
            if not self.index_file.exists():
                self.index_file.write_text(json.dumps(self.index_init_data, indent=4))

    def _get_file_path(self, key: str) -> Path:
        """Sanitizes the key to be a valid filename and returns the full path."""
        safe_key = key.replace('/', '_').replace('\\', '_')
        return self.storage_path / f"{safe_key}.json"

    def save(self, key: str, data: Dict[str, Any]) -> bool:
        """Saves data to a file atomically."""
        file_path = self._get_file_path(key)
        temp_path = file_path.with_suffix('.tmp')

        with self._lock:
            # Write to a temporary file first
            temp_path.write_text(json.dumps(data, indent=4), encoding='utf-8')
            os.replace(temp_path, file_path)  # atomic replace
            return True

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Loads data from a file."""
        file_path = self._get_file_path(key)
        with self._lock:
            if not file_path.exists():
                return None
            return json.loads(file_path.read_text(encoding='utf-8'))

    def delete(self, key: str) -> bool:
        """Deletes a file."""
        file_path = self._get_file_path(key)
        with self._lock:
            if file_path.exists():
                os.remove(file_path)
                return True
            return False

    def exists(self, key: str) -> bool:
        """Checks if a file for the given key exists."""
        return self._get_file_path(key).exists()

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """Lists all keys by listing the .json files in the storage directory."""
        with self._lock:
            return [
                f.stem
                for f in self.storage_path.glob('*.json')
                if f.is_file() and f.name != self.index_file.name
            ]

    def update(self, key: str, update_func: Callable[[Dict], Dict]) -> Optional[Dict[str, Any]]:
        """Atomically updates a record by loading, modifying, and saving it."""
        with self._lock:
            current_data = self.load(key)
            if current_data is None:
                return None
            updated_data = update_func(current_data)
            self.save(key, updated_data)
            return updated_data

    def close(self) -> None:
        """No-op for file-based storage."""
        pass