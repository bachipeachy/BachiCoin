#!/usr/bin/env python3
# sqlite_provider.py

import json
import logging
import sqlite3
import threading
from typing import Dict, Any, List, Optional

from BachiCoin.lib_storage.base_provider import StorageProvider


class SQLiteStorageProvider(StorageProvider[Dict[str, Any]]):
    """SQLite-based storage provider."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS storage (
                    key TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at REAL DEFAULT (julianday('now')),
                    updated_at REAL DEFAULT (julianday('now'))
                )
            """)
            conn.commit()

    def _get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)

    def save(self, key: str, data: Dict[str, Any]) -> bool:
        """Save data to database."""
        try:
            with self._lock:
                json_data = json.dumps(data)
                with self._get_connection() as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO storage (key, data, updated_at)
                        VALUES (?, ?, julianday('now'))
                    """, (key, json_data))
                    conn.commit()
                return True
        except Exception as e:
            logging.error(f"SQLiteStorage save error for {key}: {e}")
            return False

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        """Load data from database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT data FROM storage WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
        except Exception as e:
            logging.error(f"SQLiteStorage load error for {key}: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete data from database."""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.execute("DELETE FROM storage WHERE key = ?", (key,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logging.error(f"SQLiteStorage delete error for {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT 1 FROM storage WHERE key = ? LIMIT 1", (key,))
                return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"SQLiteStorage exists error for {key}: {e}")
            return False

    def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        """List all keys from database."""
        try:
            with self._get_connection() as conn:
                if prefix:
                    cursor = conn.execute(
                        "SELECT key FROM storage WHERE key LIKE ? ORDER BY key",
                        (f"{prefix}%",)
                    )
                else:
                    cursor = conn.execute("SELECT key FROM storage ORDER BY key")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"SQLiteStorage list_keys error: {e}")
            return []

    def update(self, key: str, update_func) -> Optional[Dict[str, Any]]:
        """Update data using function."""
        try:
            with self._lock:
                data = self.load(key)
                if data is None:
                    return None

                updated_data = update_func(data)
                if self.save(key, updated_data):
                    return updated_data
                return None
        except Exception as e:
            logging.error(f"SQLiteStorage update error for {key}: {e}")
            return None

    def close(self) -> None:
        """Close database connections."""
        pass  # Connections are managed per-operation


if __name__ == "__main__":
    import tempfile
    import os

    print("=== SQLiteStorageProvider Test ===")

    # Create temporary database file for testing
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()

    try:
        # Initialize provider
        provider = SQLiteStorageProvider(temp_db.name)
        print(f"✅ Created SQLiteStorageProvider at {temp_db.name}")

        # Test save/load cycle
        test_data = {"test_key": "test_value", "number": 42, "nested": {"data": "works"}}
        success = provider.save("test_item", test_data)
        print(f"✅ Save operation: {success}")

        loaded_data = provider.load("test_item")
        if loaded_data == test_data:
            print("✅ Load operation: Data matches")
        else:
            print(f"❌ Load operation: Data mismatch")
            print(f"   Expected: {test_data}")
            print(f"   Got: {loaded_data}")

        # Test exists
        exists = provider.exists("test_item")
        print(f"✅ Exists check: {exists}")

        # Test non-existent item
        not_exists = provider.exists("non_existent")
        print(f"✅ Non-existent check: {not not_exists}")

        # Test list_keys
        keys = provider.list_keys()
        print(f"✅ List keys: {keys}")

        # Add more test data
        provider.save("item2", {"data": "second"})
        provider.save("item3", {"data": "third"})

        all_keys = provider.list_keys()
        print(f"✅ All keys: {sorted(all_keys)}")

        # Test prefix filtering
        provider.save("test_prefix_1", {"data": "first"})
        provider.save("test_prefix_2", {"data": "second"})
        prefix_keys = provider.list_keys("test_")
        print(f"✅ Prefix keys: {sorted(prefix_keys)}")


        # Test update
        def update_func(data):
            data["updated"] = True
            data["timestamp"] = "2025-01-01"
            return data


        updated = provider.update("test_item", update_func)
        print(f"✅ Update operation: {updated is not None}")
        if updated:
            print(f"   Updated data: {updated}")

        # Test delete
        deleted = provider.delete("item2")
        print(f"✅ Delete operation: {deleted}")

        # Verify deletion
        after_delete_keys = provider.list_keys()
        print(f"✅ Keys after deletion: {sorted(after_delete_keys)}")

        print("=== SQLiteStorageProvider Test Complete ===")
        print("All database operations working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        try:
            os.unlink(temp_db.name)
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
