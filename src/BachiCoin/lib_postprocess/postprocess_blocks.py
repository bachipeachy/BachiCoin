#!/usr/bin/env python3
"""
postprocess_blocks.py - The orchestrator for processing blocks and reporting results.
It uses the state_transition library to perform calculations and then
handles all user-facing output and logging.
"""

import logging
import argparse
from typing import Dict, Optional, List

from BachiCoin.lib_postprocess.postprocess_state import (
    update_block_state,
    get_ledger_summary,
    close_services,
    UpdateResult
)
from BachiCoin.lib_postprocess.postprocess_config import DISPLAY_DECIMAL_PLACES
from BachiCoin.lib_crossmodule.node_context import NodeContext

# Direct imports for dependent services
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService # For type hinting


logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger()


def _get_block_height(block: Optional[Dict]) -> int:
    """Safely get height from either a flat or nested block."""
    if not block:
        return -1
    return block.get("header", block).get("height", -1)


def process_block(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block_hash: str
) -> bool:
    """
    Contains the core logic for processing one block.
    Returns True if the block contained transactions, False otherwise.
    Raises ValueError on processing failure.
    """
    # 1. Delegate the hard work to the "Engine"
    result: UpdateResult = update_block_state(all_node_contexts, address_to_node_map, block_hash)

    # 2. Inspect the result and fail hard if there are errors
    if result["errors"]:
        # Don't raise an error if the only error is that the block was already processed
        if len(result["errors"]) == 1 and "already processed" in result["errors"][0]:
            return False
        error_message = f"Failed to process block {result['block_hash'][:16]}. Errors: {result['errors']}"
        log.error(f"💥 {error_message}")
        raise ValueError(error_message)

    # 3. The state update function now marks the block as processed.
    return result['processed_tx_count'] > 0


def run_postprocess(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block_hash: Optional[str] = None
) -> int:
    """
    Finds and processes new blocks on the single, best canonical chain, reporting the outcome.
    """
    processed_tx_block_count = 0
    
    # 1. Find the best node context based on consensus (finalized, justified, then height).
    best_node_context = None
    best_node_id = -1
    
    node_states = []
    for node_id, context in all_node_contexts.items():
        # Use direct service calls
        finalized_block = context.blockchain_service.get_finalized_block()
        justified_block = context.blockchain_service.get_justified_block()
        height = context.blockchain_service.get_chain_height()
        node_states.append({
            "node_id": node_id,
            "context": context,
            "finalized_height": _get_block_height(finalized_block),
            "justified_height": _get_block_height(justified_block),
            "height": height
        })

    # Sort by finalized height, then justified height, then overall height (all descending).
    sorted_nodes = sorted(node_states, key=lambda x: (x['finalized_height'], x['justified_height'], x['height']), reverse=True)
    
    if not sorted_nodes:
        log.warning("  -> No nodes found to process. Skipping post-processing.")
        return 0

    best_node_state = sorted_nodes[0]
    best_node_context = best_node_state['context']
    best_node_id = best_node_state['node_id']
    
    blockchain_service = best_node_context.blockchain_service
    log.info(f"  -> Using Node {best_node_id} (H: {best_node_state['height']}, J: {best_node_state['justified_height']}, F: {best_node_state['finalized_height']}) as the source of truth.")

    blocks_to_process: List[Dict] = []

    if block_hash:
        # If a specific block is requested, process only that one if it's not already done.
        block = blockchain_service.get_block(block_hash)
        if block and not block.get("state_processed"):
            blocks_to_process.append(block)
    else:
        # 2. Walk backwards from the tip of the *best* chain to find all unprocessed canonical blocks.
        current_block = blockchain_service.get_chain_tip()
        while current_block and not current_block.get("state_processed"):
            blocks_to_process.insert(0, current_block) # Insert at the beginning to maintain forward order.
            parent_hash = current_block.get("header", current_block).get("parent_hash")
            if not parent_hash or parent_hash == "0x" + "0" * 64:
                break
            current_block = blockchain_service.get_block(parent_hash)

    if not blocks_to_process:
        return 0

    log.info(f"  -> Found {len(blocks_to_process)} new canonical block(s) to post-process.")
    for block in blocks_to_process:
        if process_block(all_node_contexts, address_to_node_map, block['block_hash']):
            processed_tx_block_count += 1
    
    if processed_tx_block_count > 0:
        log.info(f"  -> Finished processing {processed_tx_block_count} block(s) with transactions.")

    return processed_tx_block_count


if __name__ == '__main__':
    from tests.test_config import dirs

    parser = argparse.ArgumentParser(description="BachiCoin Block Post-Processor.")
    parser.add_argument('--block-hash', type=str, help='The hash of a single block to process.')
    args = parser.parse_args()

    print("\n🔹 Initializing services for post-processing smoke test...")
    
    # Create services using factories
    user_service = UserServiceFactory.create_user_index_service(dirs)
    wallet_service = WalletServiceFactory.create_wallet_index_service(dirs, user_service=user_service)
    blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(dirs)
    tx_service = TxServiceFactory.create_tx_index_service(dirs, wallet_index_service=wallet_service)

    test_node_context = NodeContext(
        node_dirs=dirs,
        user_service=user_service,
        wallet_service=wallet_service,
        blockchain_service=blockchain_service,
        tx_service=tx_service
    )

    mock_all_node_contexts = {0: test_node_context}
    mock_address_to_node_map = {}
    wallet_summaries = test_node_context.wallet_service.list_wallets()
    for summary in wallet_summaries:
        wallet_id = summary.get("wallet_id")
        if wallet_id:
            wallet_data = test_node_context.wallet_service.get_wallet(wallet_id) # Corrected call
            if wallet_data and wallet_data.get("address"):
                mock_address_to_node_map[wallet_data["address"]] = 0

    try:
        run_postprocess(mock_all_node_contexts, mock_address_to_node_map, args.block_hash)
    except ValueError as e:
        log.error(f"\n--- Post-processing failed as expected in smoke test: {e} ---")

    final_summary = get_ledger_summary(mock_all_node_contexts)
    print(
        f"\n✅ System Final State: {final_summary['total_balance']:.{DISPLAY_DECIMAL_PLACES}f} BACHI across {final_summary['wallet_count']} wallets.\n")

    close_services(mock_all_node_contexts)
    print("\n🎯 Done.")
