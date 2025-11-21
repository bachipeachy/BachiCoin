#!/usr/bin/env python3
"""id_generator.py - Centralized utility for creating deterministic, content-addressable IDs."""

import json
import hashlib
from typing import Dict, Any

def generate_hash_id(prefix: str, data: Dict[str, Any], length: int = 16) -> str:
    """
    Generates a deterministic, content-addressable ID from a dictionary of data.

    Args:
        prefix: A short prefix for the ID (e.g., "U" for User, "W" for Wallet).
        data: A dictionary of properties that uniquely define the entity.
        length: The number of characters from the hash to use in the final ID.

    Returns:
        A deterministic ID string (e.g., "U_a94d9554fa3dfe35").
    """
    # Canonicalize the data by sorting keys and converting to a compact JSON string
    canonical_string = json.dumps(data, sort_keys=True, separators=(",", ":"))
    
    # Hash the canonical string using SHA256
    hasher = hashlib.sha256()
    hasher.update(canonical_string.encode('utf-8'))
    hex_digest = hasher.hexdigest()
    
    # Return the formatted ID
    return f"{prefix}_{hex_digest[:length]}"


if __name__ == "__main__":
    """Smoke test to verify the functionality and determinism of the ID generator."""
    print("=== ID Generator Smoke Test ===")

    # --- Test User ID Generation ---
    user1_data = {'kyc_data': 'gomer.adams@bachicoin.org'}
    user1_id = generate_hash_id("U", user1_data)
    print(f"User 1 Data: {user1_data}")
    print(f"User 1 ID:   {user1_id}")

    user2_data = {'kyc_data': 'liam.adams@bachicoin.org'}
    user2_id = generate_hash_id("U", user2_data)
    print(f"User 2 Data: {user2_data}")
    print(f"User 2 ID:   {user2_id}")

    # --- Test Wallet ID Generation ---
    wallet1_data = {'user_id': user1_id, 'wallet_type': 'private'}
    wallet1_id = generate_hash_id("W", wallet1_data)
    print(f"Wallet 1 Data: {wallet1_data}")
    print(f"Wallet 1 ID:   {wallet1_id}")

    wallet2_data = {'user_id': user1_id, 'wallet_type': 'business'}
    wallet2_id = generate_hash_id("W", wallet2_data)
    print(f"Wallet 2 Data: {wallet2_data}")
    print(f"Wallet 2 ID:   {wallet2_id}")

    # --- Test Node ID Generation ---
    node1_data = {'host': '127.0.0.1', 'port': 9333}
    node1_id = generate_hash_id("N", node1_data)
    print(f"Node 1 Data: {node1_data}")
    print(f"Node 1 ID:   {node1_id}")

    # --- Test Determinism ---
    print(f"\nRe-generating User 1 ID: {generate_hash_id('U', user1_data)}")
    assert user1_id == generate_hash_id("U", user1_data), "Determinism check failed!"
    print("✅ Determinism check passed.")

    print("\n✅ ID Generator Smoke Test Passed!")
