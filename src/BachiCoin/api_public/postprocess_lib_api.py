#!/usr/bin/env python3
"""postprocess_lib_api.py - Public API wrapper for functional state transition."""

from typing import Dict, Optional
from BachiCoin.lib_postprocess import postprocess_state as state_transition
from BachiCoin.lib_postprocess import postprocess_blocks as postprocess
from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_postprocess.postprocess_config import DISPLAY_DECIMAL_PLACES as _DISPLAY_DECIMAL_PLACES
DISPLAY_DECIMAL_PLACES = _DISPLAY_DECIMAL_PLACES

# --- Direct imports from the state engine ---
from BachiCoin.lib_postprocess.postprocess_state import (
    get_ledger_summary
)
from BachiCoin.lib_postprocess.postprocess_blocks import close_services as _close_services
close_services = _close_services


# Public API wrappers (functional)

def display_user_wallet_summary(all_node_contexts: Dict[int, NodeContext], header: str) -> None:
    """Print a detailed summary of all users and wallets across all nodes."""
    print(f"\n--- {header} ---")
    summary = get_ledger_summary(all_node_contexts)
    print(f"Total Ledger Balance: {summary.get('total_balance', 0.0):.{DISPLAY_DECIMAL_PLACES}f} BACHI")
    print(f"Total Wallets: {summary.get('wallet_count', 0)}")
    print(f"Total Users: {summary.get('user_count', 0)}")
    print("-" * 50)


def get_total_wallet_balance(all_node_contexts: Dict[int, NodeContext]) -> float:
    """Compute total balance across all wallets on all nodes."""
    return state_transition.get_ledger_balance(all_node_contexts)


def run_postprocess(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block_hash: Optional[str] = None
) -> int:
    """Runs the post-processing logic for blocks using a decentralized context."""
    return postprocess.run_postprocess(all_node_contexts, address_to_node_map, block_hash)

# The close_services function is imported directly and exposed.
