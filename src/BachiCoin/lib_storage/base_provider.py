#!/usr/bin/env python3
# base_provider.py

from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic

T = TypeVar('T')


class StorageProvider(ABC, Generic[T]):
    """All storage implementations must implement this interface."""

    @abstractmethod
    def save(self, key: str, data: T) -> bool:
        """Save data with key. Returns success status."""
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[T]:
        """Load data by key. Returns None if not found."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete data by key. Returns success status."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abstractmethod
    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys, optionally filtered by prefix."""
        pass

    @abstractmethod
    def update(self, key: str, update_func) -> Optional[T]:
        """Update data using function. Returns updated data or None."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        pass


if __name__ == "__main__":
    print("=== StorageProvider Base Class Test ===")
    abstract_methods = StorageProvider.__abstractmethods__
    print(f"✅ All {len(abstract_methods)} abstract methods defined")
    for method in sorted(abstract_methods):
        print(f"   • {method}")
