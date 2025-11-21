#!/usr/bin/env python3
"""
blockchain_merkle_verkle.py - Calculate hybrid Merkle/Verkle roots for block data.
"""

from typing import List, Dict, Any
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils

def calculate_txs_root(txs: List[Dict[str, Any]]) -> str:
    """
    Calculate txs_root: Merkle‑style placeholder hash of tx_hash list.
    """
    if not txs:
        return "0x" + "0" * 64

    tx_hashes = [tx.get("tx_hash", "") for tx in txs]
    combined = "".join(sorted(tx_hashes))
    hash_bytes = CryptoUtils.hash_data(combined, "sha256")
    return "0x" + hash_bytes.hex()


def calculate_receipts_root(receipts: List[Dict[str, Any]]) -> str:
    """
    Calculate receipts_root: Merkle‑style placeholder hash of receipt hashes.
    """
    if not receipts:
        return "0x" + "0" * 64

    receipt_hashes = [receipt.get("receipt_hash", "") for receipt in receipts]
    combined = "".join(sorted(receipt_hashes))
    hash_bytes = CryptoUtils.hash_data(combined, "sha256")
    return "0x" + hash_bytes.hex()


def calculate_state_root(state_entries: List[Dict[str, Any]]) -> str:
    """
    Calculate state_root: Verkle‑style placeholder hash over state entries.
    Example: hash address:balance pairs.
    """
    if not state_entries:
        return "0x" + "0" * 64

    raw_items = [
        f"{entry.get('address','')}:{entry.get('balance',0)}"
        for entry in state_entries
    ]
    combined = "".join(sorted(raw_items))
    hash_bytes = CryptoUtils.hash_data(combined, "sha256")
    return "0x" + hash_bytes.hex()


def calculate_all_roots(
    txs: List[Dict[str, Any]],
    receipts: List[Dict[str, Any]],
    state_entries: List[Dict[str, Any]]
) -> Dict[str, str]:
    """
    Compute all three roots in one shot.
    """
    return {
        "txs_root": calculate_txs_root(txs),
        "receipts_root": calculate_receipts_root(receipts),
        "state_root": calculate_state_root(state_entries),
    }

if __name__ == "__main__":
    print("✅ Running simple unit test for merkle_verkle_roots...")

    # Sample dummy txs
    txs = [
        {"tx_hash": "0xaaa111"},
        {"tx_hash": "0xbbb222"},
    ]

    # Sample dummy receipts
    receipts = [
        {"receipt_hash": "0xccc333"},
        {"receipt_hash": "0xddd444"},
    ]

    # Sample dummy state entries
    state = [
        {"address": "0x111", "balance": 500},
        {"address": "0x222", "balance": 900},
    ]

    roots = calculate_all_roots(txs, receipts, state)

    print(f"\nMerkle transactions root: {roots['txs_root']}")
    print(f"Merkle receipts root    : {roots['receipts_root']}")
    print(f"Verkle state root       : {roots['state_root']}")
