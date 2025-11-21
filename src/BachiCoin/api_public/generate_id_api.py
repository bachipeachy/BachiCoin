#!/usr/bin/env python3
"""id_generator_api.py - Public API wrapper for the ID generation utility."""

# Import the concrete implementation
from typing import Dict, Any
from BachiCoin.lib_crossmodule.id_generator import generate_hash_id as generate_id

def generate_hash_id(prefix: str, entropy_digits: Dict[str, Any] = 3) -> str:
    """Generates a time-based randomized unique ID."""
    return generate_id(prefix, entropy_digits)

if __name__ == "__main__":
    """A simple smoke test for the public ID generation API."""
    print("--- Running generate_id_api.py Smoke Test ---")
    test_id = generate_hash_id("U")
    assert test_id.startswith("U"), "Prefix was not applied correctly."
    print(f"✅ Successfully generated a test ID: {test_id}")
    print("--- Smoke Test Passed ---")
