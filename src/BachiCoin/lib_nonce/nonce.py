#!/usr/bin/env python3
"""lib_nonce.py - Nonce management service (ETH-style, clean, fail-fast)"""

from typing import List, Dict, Any
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService


def get_nonce(address: str, wallet_service: WalletIndexService) -> int:
    """Return confirmed canonical nonce from wallet index"""
    wallet_id = wallet_service.get_wallet_id_by_address(address)
    assert wallet_id, f"Wallet not found for address: {address}"

    wallet_summary = wallet_service.get_wallet_summary(wallet_id)
    assert wallet_summary, f"Wallet summary missing for {wallet_id}"

    return wallet_summary.get("nonce", 0)


def get_pending_nonces(pending_txs: List[Dict[str, Any]]) -> List[int]:
    """Return sorted list of pending nonces from transaction list filtering None value or no nonce"""
    return sorted(tx["nonce"] for tx in pending_txs if "nonce" in tx and tx["nonce"] is not None)


def calculate_next_nonce(
    address: str, wallet_service: WalletIndexService, pending_txs: List[Dict[str, Any]]
) -> int:
    """
    Calculates the next nonce for a new transaction.
    The next nonce should be the maximum of the last confirmed (canonical) nonce
    and any pending nonces in the mempool, plus one.
    This prevents gaps and ensures sequential ordering.
    """
    canonical_nonce = get_nonce(address, wallet_service)
    pending_nonces = get_pending_nonces(pending_txs)

    # If there are no pending transactions with valid nonces, the next nonce is simply the canonical nonce.
    if not pending_nonces:
        return canonical_nonce

    # The next nonce is the highest pending nonce + 1.
    # This correctly handles cases where the mempool might have nonce gaps.
    highest_pending = max(pending_nonces)
    
    # The next nonce must be at least the canonical nonce.
    # It should be the highest known nonce (either on-chain or in-mempool) + 1.
    return max(canonical_nonce, highest_pending + 1)


def increment_nonce(address: str, wallet_service: WalletIndexService, tx_count: int = 0) -> None:
    """After block confirmation: advance canonical nonce by number of pending txs."""
    wallet_id = wallet_service.get_wallet_id_by_address(address)
    assert wallet_id, f"Wallet not found for address: {wallet_id}"
    canonical = get_nonce(address, wallet_service)
    new_nonce = canonical + tx_count
    updated = wallet_service.update_account_state(wallet_id, nonce=new_nonce)
    assert updated, f"Failed to update nonce for wallet {wallet_id}"
