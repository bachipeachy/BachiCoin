#!/usr/bin/env python3
"""blockchain_builder.py - Pure block construction utilities (no side-effects).

Responsibilities:
- Prepare block dictionaries for genesis and consensus blocks.
- Calculate derived block fields (gas, base fee, etc).
- Return block_data dict to caller; caller is responsible for persisting.
"""

import time
from typing import Dict, Any, List

from BachiCoin.lib_blockchain.blockchain_config import (
    calculate_next_base_fee,
    calculate_gas_used,
    calculate_total_fees,
    ConsensusType,
    BlockchainConfig,
    generate_block_hash,
)
from BachiCoin.lib_blockchain.blockchain_merkle_verkle import (
    calculate_txs_root,
)

# ============================================================================
# GENESIS MANAGEMENT (PURE)
# ============================================================================

def prepare_genesis_block_data(network: str) -> Dict[str, Any]:
    """Return genesis block data (pure). Caller persists and updates chain state.
    - network: network name (e.g. "testnet")
    """
    genesis_data = {
        "parent_hash": "0x" + "0" * 64,
        "height": 0,
        "slot": 0,
        "epoch": 0,
        "proposer_index": 0,
        "randao_reveal": "0x" + "0" * 96,
        "block_type": "genesis",
        "network": network,
        "transactions": [],
        "transaction_count": 0,
        "gas_limit": BlockchainConfig.DEFAULT_GAS_LIMIT,
        "gas_used": 0,
        "base_fee_per_gas": BlockchainConfig.MIN_BASE_FEE,
        "timestamp": int(time.time()),
        "status": "finalized",
        "is_canonical": True,
        "extra_data": f"Genesis - {network}".encode(),
        "difficulty": 0,
    }
    return genesis_data


# ============================================================================
# CONSENSUS BLOCK BUILDING (PURE)
# ============================================================================

def prepare_consensus_block_data(
        parent_block: Dict[str, Any],
        slot: int,
        epoch: int,
        proposer_index: int,
        transactions: List[Dict[str, Any]],
        network: str
) -> Dict[str, Any]:
    """Construct a consensus block payload (pure). Caller persists and updates chain state.

    Args:
        parent_block: existing chain tip block dict (must include height, gas_limit, base_fee_per_gas)
        slot: slot number
        epoch: epoch number
        proposer_index: proposer validator index
        transactions: list of tx dicts (may include gas_limit fields)
        network: network name

    Returns:
        block_data: dict ready to be passed to storage layer (create_block_with_index)
    """
    assert parent_block is not None, "parent_block is required"
    parent_hash = parent_block.get("block_hash") or parent_block.get("hash") or parent_block.get("parent_hash")
    current_height = parent_block.get("height", -1)
    next_height = current_height + 1

    # Calculate next base fee using parent info
    next_base_fee = calculate_next_base_fee(
        parent_block.get("gas_used", 0),
        parent_block.get("gas_limit", BlockchainConfig.DEFAULT_GAS_LIMIT),
        parent_block.get("base_fee_per_gas", BlockchainConfig.MIN_BASE_FEE),
    )

    total_gas_used = calculate_gas_used(transactions)

    block_data = {
        "parent_hash": parent_hash,
        "height": next_height,
        "block_type": "regular",
        "network": network,
        "timestamp": int(time.time()),
        "transactions": transactions,
        "transaction_count": len(transactions),
        "gas_limit": parent_block.get("gas_limit", BlockchainConfig.DEFAULT_GAS_LIMIT),
        "gas_used": total_gas_used,
        "base_fee_per_gas": next_base_fee,
        "slot": slot,
        "epoch": epoch,
        "proposer_index": proposer_index,
        "consensus_type": ConsensusType.PROOF_OF_STAKE.value,
        "status": "proposed",
        "is_canonical": True,
        "extra_data": f"ETH 2.0 Block - Slot {slot}".encode(),
        "difficulty": 0,
    }

    # Calculate computed roots if needed
    if not block_data.get("transactions_root") and transactions:
        block_data["transactions_root"] = calculate_txs_root(transactions)
    else:
        block_data["transactions_root"] = "0x" + "0" * 64

    # Calculate total fees using EIP-1559 method
    if not block_data.get("total_fees"):
        block_data["total_fees"] = calculate_total_fees(transactions)

    # Generate block hash LAST (after all other fields are set)
    return block_data

# ============================================================================
# Optional small helpers (pure)
# ============================================================================

def validate_consensus_block_params(slot: int, epoch: int, proposer_index: int,
                                    transactions: List[Dict[str, Any]]) -> bool:
    """Validate consensus block parameters before building (pure)."""
    assert slot >= 0, f"Invalid slot: {slot}"
    assert epoch >= 0, f"Invalid epoch: {epoch}"
    assert proposer_index >= 0, f"Invalid proposer index: {proposer_index}"
    assert isinstance(transactions, list), "Transactions must be list"
    for i, tx in enumerate(transactions):
        assert isinstance(tx, dict), f"Transaction {i} must be dict"
    return True


if __name__ == "__main__":
    """KISS unit test for the blockchain builder."""
    print("=== Blockchain Builder (Pure Functions) KISS Test ===")

    # 1. Test Genesis Block Preparation
    print("\n🧪 1. Testing Genesis Block Preparation...")
    genesis_block = prepare_genesis_block_data("testnet")
    assert genesis_block is not None
    assert genesis_block["height"] == 0
    print("✅ Genesis block prepared successfully.")

    # 2. Test Consensus Block Preparation
    print("\n🧪 2. Testing Consensus Block Preparation...")
    # Use the genesis block as the parent for the test
    parent_block = genesis_block
    test_txs = [{"tx_hash": "0x" + "c" * 64, "gas_limit": 21000, "max_fee_per_gas": 50, "max_priority_fee_per_gas": 2}]
    consensus_block = prepare_consensus_block_data(
        parent_block=parent_block,
        slot=1,
        epoch=0,
        proposer_index=1,
        transactions=test_txs,
        network="testnet"
    )
    assert consensus_block is not None
    assert consensus_block["height"] == 1
    print("✅ Consensus block prepared successfully.")

    print("\n🎉 Blockchain Builder Test Complete!")