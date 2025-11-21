#!/usr/bin/env python3
"""nonce_lib_api.py - Public API wrapper for the Nonce module."""

from typing import List, Dict, Any

# Import the concrete implementation
from BachiCoin.lib_nonce import nonce
from BachiCoin.api_public.wallet_lib_api import WalletIndexService

# Public API functions wrapping the nonce logic
def get_nonce(address: str, wallet_service: WalletIndexService) -> int:
    """Return confirmed canonical nonce from wallet index"""
    return nonce.get_nonce(address, wallet_service)

def get_pending_nonces(pending_txs: List[Dict[str, Any]]) -> List[int]:
    """Return sorted list of pending nonces from a given list of transactions."""
    return nonce.get_pending_nonces(pending_txs)


def calculate_next_nonce(
    address: str, wallet_service: WalletIndexService, pending_txs: List[Dict[str, Any]]
) -> int:
    """next nonce = canonical_nonce + number of pending txs in mempool"""
    return nonce.calculate_next_nonce(address, wallet_service, pending_txs)


def increment_nonce(address: str, wallet_service: WalletIndexService, tx_count: int = 0) -> None:
    """After block confirmation: advance canonical nonce by number of pending txs."""
    nonce.increment_nonce(address, wallet_service, tx_count)
