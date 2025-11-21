#!/usr/bin/env python3
"""tx_signer.py: Signs and verifies BachiCoin transactions."""

import json
import sys
from typing import Dict, Any, Optional

from BachiCoin.lib_transaction.tx_config import TxConfig, TxType
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils


def get_canonical_tx_data(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Filters and sorts transaction fields according to the canonical list for hashing.
    Fields not in the canonical list are excluded. Missing canonical fields are set to None.
    """
    canonical_fields = TxConfig.SCHEMA_VIEWS["canonical"]
    canonical_data = {}
    for field in canonical_fields:
        # Use .get() to safely retrieve values; missing fields will be None
        canonical_data[field] = tx.get(field)
    return canonical_data

def create_canonical_tx_hash(tx_data: Dict[str, Any]) -> str:
    """Creates a canonical hash for a transaction, returning a hex string with '0x' prefix.
    The hash is computed from a JSON-serialized representation of canonical transaction fields.
    """
    canonical_tx = get_canonical_tx_data(tx_data)
    # Ensure deterministic JSON serialization for consistent hashing
    canonical_json = json.dumps(canonical_tx, sort_keys=True, separators=(',', ':'))
    hash_bytes = CryptoUtils.hash_data(canonical_json.encode('utf-8')) # Encode to bytes
    return "0x" + hash_bytes.hex()

def verify_transaction_signature(tx_data: Dict[str, Any]) -> bool:
    """Verifies the signature of a transaction by re-calculating the hash and recovering the public key."""
    signature = tx_data.get("signature")
    from_address = tx_data.get("from_address")

    if not all([signature, from_address]):
        return False

    # Use the new canonical hash creation for verification
    tx_hash_to_verify = create_canonical_tx_hash(tx_data)
    tx_hash_bytes = bytes.fromhex(tx_hash_to_verify.replace("0x", ""))

    # Strip "0x" prefix from signature before passing to crypto utility
    if signature.startswith("0x"):
        signature = signature[2:]

    recovered_pub_key = CryptoUtils.recover_public_key(tx_hash_bytes, signature)
    if not recovered_pub_key:
        return False

    recovered_address = CryptoUtils.public_key_to_address(recovered_pub_key)
    
    return recovered_address.lower() == from_address.lower()

def get_signing_address_from_tx(tx_data: Dict[str, Any]) -> Optional[str]:
    """Extracts the sender's address from the transaction data, if present."""
    return tx_data.get("from_address")


if __name__ == '__main__':
    print("--- Smoke Test for tx_signer.py ---")

    test_private_key = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d734123f129"
    expected_address = "0xbcd09f92fd6035e42d5f287955ea0186eb0136ab"
    to_addr = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"

    sample_transfer_tx = {
        "chain_id": 1337,
        "nonce": 0,
        "max_priority_fee_per_gas": 2.0,
        "max_fee_per_gas": 40.0,
        "gas_limit": 21000,
        "to_address": to_addr,
        "from_address": expected_address,
        "amount": 1.0,
        "data": "0x",
        "access_list": [],
        "tx_type": "transfer",
        "network": "testnet",
        "tx_version": 0, # Added for canonical hashing
        "currency": "BACHI", # Added for canonical hashing
        "memo": "", # Added for canonical hashing
        "timestamp": "2023-01-01T00:00:00Z", # Added for canonical hashing
        "created_at": "2023-01-01T00:00:00Z" # Added for canonical hashing
    }

    print("\n1. Testing get_canonical_tx_data...")
    canonical_data = get_canonical_tx_data(sample_transfer_tx)
    expected_canonical_fields = sorted(TxConfig.SCHEMA_VIEWS["canonical"])
    assert list(canonical_data.keys()) == expected_canonical_fields, \
        f"Canonical data keys mismatch. Expected {expected_canonical_fields}, got {list(canonical_data.keys())}"
    assert canonical_data["tx_version"] == 0, "tx_version not correctly included in canonical data."
    print("   PASS: get_canonical_tx_data works as expected.")

    print("\n2. Testing create_canonical_tx_hash...")
    tx_hash = create_canonical_tx_hash(sample_transfer_tx)
    print(f"   Transaction Hash: {tx_hash}")
    assert tx_hash.startswith("0x") and len(tx_hash) == 66, "Hash should be 0x-prefixed and 66 chars long."
    print("   PASS: Canonical hash created successfully.")

    print("\n3. Testing signature and verification with canonical hash...")
    try:
        signature_hex_no_prefix = CryptoUtils.sign_message_recoverable(bytes.fromhex(tx_hash[2:]), test_private_key)
        signed_tx = sample_transfer_tx.copy()
        signed_tx['signature'] = "0x" + signature_hex_no_prefix
        
        is_valid = verify_transaction_signature(signed_tx)
        print(f"   Signature is valid: {is_valid}")
        assert is_valid, "Signature verification failed."
        print("   PASS: Signature verified successfully using canonical hash.")
    except Exception as e:
        print(f"   FAIL: Verification failed - {e}")
        sys.exit(1)

    print("\n4. Testing get_signing_address_from_tx...")
    extracted_address = get_signing_address_from_tx(sample_transfer_tx)
    print(f"   Extracted Address: {extracted_address}")
    assert extracted_address.lower() == expected_address.lower(), "Extracted address does not match original."
    print("   PASS: Signing address extracted successfully.")

    print("\n5. Testing a MINT transaction (which should not verify)...")
    sample_mint_tx = {
        "tx_type": TxType.MINT.value,
        "to_address": to_addr,
        "amount": 1000.0,
        "signature": "0x" + "f" * 130, # Dummy signature
        "from_address": None, # Explicitly None
        "nonce": None,        # Explicitly None
        "chain_id": 1337,
        "tx_version": 0,
        "gas_limit": 0,
        "max_fee_per_gas": 0,
        "max_priority_fee_per_gas": 0,
        "currency": "BACHI",
        "network": "testnet",
        "data": "0x",
        "access_list": [],
        "memo": "",
        "timestamp": "2023-01-01T00:00:00Z",
        "created_at": "2023-01-01T00:00:00Z"
    }
    is_valid_mint = verify_transaction_signature(sample_mint_tx)
    assert not is_valid_mint, "A mint transaction should not be verifiable by this function."
    print("   PASS: Correctly identified mint transaction as not verifiable.")

    print("\n--- Smoke Test Completed Successfully for tx_signer.py ---")
