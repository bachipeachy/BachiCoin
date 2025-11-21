#!/usr/bin/env python3
"""blockchain_lib_api.py - Canonical public API for BlockchainIndexService."""

import sys
from typing import Dict, Any, List, Optional, Tuple
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_blockchain.blockchain_builder import prepare_genesis_block_data as builder_prepare_genesis
from BachiCoin.lib_blockchain.blockchain_builder import prepare_consensus_block_data as builder_prepare_consensus
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg

# ============================================================================
# FACTORY (always start with this if you need explicit service)
# ============================================================================

def create_blockchain_index_service(*args, **kwargs) -> BlockchainIndexService:
    """
    Creates and initializes a fully configured BlockchainIndexService using BlockchainServiceFactory.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(BlockchainServiceFactory.create_blockchain_index_service, *args, **kwargs)

# ============================================================================
# ✅ CORE CRUD & CHAIN STATUS - Used by cross-module + REST
# ============================================================================

def create_block_with_index(service: BlockchainIndexService, block_data: Dict[str, Any]) -> str:
    """Add new block, return block hash"""
    return service.create_block_with_index(block_data)

def get_block(service: BlockchainIndexService, block_hash: str) -> Optional[Dict[str, Any]]:
    """Fetch block by hash"""
    return service.get_block(block_hash)

def get_block_by_height(service: BlockchainIndexService, height: int) -> Optional[Dict[str, Any]]:
    """Fetch block by chain height"""
    return service.get_block_by_height(height)

def get_chain_tip(service: BlockchainIndexService) -> Optional[Dict[str, Any]]:
    """Get latest block on the canonical chain"""
    return service.get_chain_tip()

def get_chain_height(service: BlockchainIndexService) -> int:
    """Get current chain height (integer)"""
    return service.get_chain_height()

def get_finalized_block(service: BlockchainIndexService) -> Optional[Dict[str, Any]]:
    """Get finalized block (ETH2)"""
    return service.get_finalized_block()

def get_justified_block(service: BlockchainIndexService) -> Optional[Dict[str, Any]]:
    """Get justified block (ETH2)"""
    return service.get_justified_block()

def get_safe_block(service: BlockchainIndexService) -> Optional[Dict[str, Any]]:
    """Get safe block (chain safety heuristic)"""
    return service.get_safe_block()

def get_nonce_and_balance(service: BlockchainIndexService, address: str) -> Dict[str, Any]:
    """
    Retrieves the canonical account state (nonce, balance) for a given address
    from the latest finalized or chain tip block's state trie.
    """
    return service.get_nonce_and_balance(address)

# ============================================================================
# 🧱 BLOCK BUILDING - Used by Consensus Orchestrator
# ============================================================================

def prepare_genesis_block_data(network: str) -> Dict[str, Any]:
    """Prepare genesis block data (pure)."""
    return builder_prepare_genesis(network)

def prepare_consensus_block_data(
        parent_block: Dict[str, Any],
        slot: int,
        epoch: int,
        proposer_index: int,
        transactions: List[Dict[str, Any]],
        network: str
) -> Dict[str, Any]:
    """Construct a consensus block payload (pure)."""
    return builder_prepare_consensus(
        parent_block, slot, epoch, proposer_index, transactions, network
    )

# ============================================================================
# 📊 LISTING & FILTERING (REST-friendly)
# ============================================================================

def list_blocks(service: BlockchainIndexService, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List blocks with pagination"""
    return service.list_blocks(limit, offset)

def get_blocks_by_status(service: BlockchainIndexService, status: str) -> List[Dict[str, Any]]:
    """Fetch blocks by status (e.g., pending, confirmed)"""
    return service.get_blocks_by_status(status)

def get_blocks_by_height_range(service: BlockchainIndexService, start_height: int, end_height: int) -> List[Dict[str, Any]]:
    """Fetch blocks in height range [start, end]"""
    return service.get_blocks_by_height_range(start_height, end_height)

def get_blocks_by_slot_range(service: BlockchainIndexService, start_slot: int, end_slot: int) -> List[Dict[str, Any]]:
    """Fetch blocks by slot range (ETH2 slot numbers)"""
    return service.get_blocks_by_slot_range(start_slot, end_slot)


# ============================================================================
# 🌳 STATE, TRIE & VERKLE - Advanced, mostly internal
# ============================================================================

def save_transaction_trie(service: BlockchainIndexService, block_hash: str, tx_trie_root: str, transactions: List[Dict[str, Any]]) -> bool:
    """Store transaction trie for a block"""
    return service.save_transaction_trie(block_hash, tx_trie_root, transactions)

def get_transaction_trie(service: BlockchainIndexService, tx_trie_root: str) -> Optional[Dict[str, Any]]:
    """Fetch transaction trie by root hash"""
    return service.get_transaction_trie(tx_trie_root)

def save_receipt_trie(service: BlockchainIndexService, block_hash: str, receipt_trie_root: str, receipts: List[Dict[str, Any]]) -> bool:
    """Store receipt trie"""
    return service.save_receipt_trie(block_hash, receipt_trie_root, receipts)

def get_receipt_trie(service: BlockchainIndexService, receipt_trie_root: str) -> Optional[Dict[str, Any]]:
    """Fetch receipt trie"""
    return service.get_receipt_trie(receipt_trie_root)

def save_state_trie(service: BlockchainIndexService, block_hash: str, state_root: str, state_data: Dict[str, Any], verkle_proof: Optional[bytes] = None) -> bool:
    """Store state trie (optionally with Verkle proof)"""
    return service.save_state_trie(block_hash, state_root, state_data, verkle_proof)

def get_state_trie(service: BlockchainIndexService, state_root: str) -> Optional[Dict[str, Any]]:
    """Fetch state trie by root hash"""
    return service.get_state_trie(state_root)

def save_verkle_proof(service: BlockchainIndexService, proof_id: str, proof_data: bytes, metadata: Dict[str, Any] = None) -> bool:
    """Store Verkle proof blob & metadata"""
    return service.save_verkle_proof(proof_id, proof_data, metadata)

def get_verkle_proof(service: BlockchainIndexService, proof_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
    """Fetch Verkle proof & metadata by ID"""
    return service.get_verkle_proof(proof_id)


# ============================================================================
# 🛠 ADMIN / MAINTENANCE - Rarely used in live path
# ============================================================================

def update_block(service: BlockchainIndexService, block_hash: str, updates: Dict[str, Any]) -> bool:
    """Update block fields (admin)"""
    return service.update_block(block_hash, updates)

def delete_block(service: BlockchainIndexService, block_hash: str) -> bool:
    """Delete block by hash (dangerous, admin)"""
    return service.delete_block(block_hash)

def update_chain_state(service: BlockchainIndexService, updates: Dict[str, Any]) -> bool:
    """Update global chain state (admin)"""
    return service.update_chain_state(updates)

def set_chain_tip(service: BlockchainIndexService, block_hash: str, height: int) -> bool:
    """Atomically sets the chain tip hash and height."""
    return service.set_chain_tip(block_hash, height)

def get_index_statistics(service: BlockchainIndexService) -> Dict[str, Any]:
    """Return index stats / counters"""
    return service.get_index_statistics()

def rebuild_index(service: BlockchainIndexService) -> Dict[str, Any]:
    """Full rebuild of blockchain index"""
    return service.rebuild_index()

def cleanup_orphaned_entries(service: BlockchainIndexService) -> Dict[str, Any]:
    """Remove orphaned index entries (cleanup)"""
    return service.cleanup_orphaned_entries()
