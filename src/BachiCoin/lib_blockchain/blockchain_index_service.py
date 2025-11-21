#!/usr/bin/env python3
"""blockchain_index_service.py - delegates pure computations to blockchain_helper."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from BachiCoin.lib_blockchain.blockchain_storage_adapter import BlockchainStorageAdapter
from BachiCoin.lib_blockchain.blockchain_config import (
    BlockStatus
)

# helpers (pure functions)
from BachiCoin.lib_blockchain.blockchain_helper import (
    prepare_block_for_storage_and_index,
    build_index_entry_from_block,
    get_default_for_index_field,
)

class BlockchainIndexService:
    def __init__(self, storage_adapter: BlockchainStorageAdapter):
        """Initializes the BlockchainIndexService."""
        self.storage = storage_adapter

    def create_block_with_index(self, block_data: Dict[str, Any]) -> str:
        """Create new block with index using block_data."""
        prepared = prepare_block_for_storage_and_index(block_data)
        block = prepared["block"]
        serializable = prepared["serializable"]
        block_hash = block["block_hash"]
        assert self.storage.save_block(block_hash, serializable), f"Failed to save block {block_hash}"
        assert self._create_index_entry(block), f"Failed to create index for {block_hash}"
        return block_hash

    def get_block(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """Get block by hash"""
        assert block_hash, "Block hash required"
        return self.storage.load_block(block_hash)

    def update_block(self, block_hash: str, updates: Dict[str, Any]) -> bool:
        """Update block and index atomically"""
        assert block_hash, "Block hash required"
        assert isinstance(updates, dict), "Updates must be dictionary"

        updates["last_modified"] = datetime.now().isoformat() + "Z"

        def apply_updates(block_data):
            block_data.update(updates)
            return block_data

        updated_block = self.storage.update_block(block_hash, apply_updates)
        assert updated_block, f"Failed to update block {block_hash}"

        assert self._update_index_entry(block_hash, updates), f"Failed to update index for {block_hash}"
        return True

    def delete_block(self, block_hash: str) -> bool:
        """Delete block and index entry atomically"""
        assert block_hash, "Block hash required"
        block_data = self.storage.load_block(block_hash)
        assert block_data, f"Block {block_hash} not found"

        assert self._remove_index_entry(block_hash), f"Failed to remove index for {block_hash}"

        if not self.storage.delete_block(block_hash):
            # Rollback index entry
            self._create_index_entry(block_data)
            assert False, f"Failed to delete block {block_hash}"

        return True

    def block_exists(self, block_hash: str) -> bool:
        """Check if block exists"""
        assert block_hash, "Block hash required"
        return self.storage.block_exists(block_hash)

    # =================== PUBLIC API: QUERY OPERATIONS ===================

    def get_block_by_height(self, height: int) -> Optional[Dict[str, Any]]:
        """Get canonical block by height"""
        assert height >= 0, "Height must be non-negative"
        block_hash = self._get_canonical_block_hash_by_height(height)
        if not block_hash:
            return None
        return self.storage.load_block(block_hash)

    def get_blocks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get blocks by ETH-aligned status"""
        assert status in [s.value for s in BlockStatus], f"Invalid status: {status}"
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return []

        matching = []
        for block, info in index_data["blocks"].items():
            if info.get("status") == status:
                blk = self.storage.load_block(block)
                if blk:
                    matching.append(blk)
        matching.sort(key=lambda x: x.get("height", 0))
        return matching

    def get_blocks_by_height_range(self, start_height: int, end_height: int) -> List[Dict[str, Any]]:
        assert start_height >= 0 and end_height >= start_height, "Invalid height range"
        blocks = []
        for h in range(start_height, end_height + 1):
            b = self.get_block_by_height(h)
            if b:
                blocks.append(b)
        return blocks

    def get_blocks_by_slot_range(self, start_slot: int, end_slot: int) -> List[Dict[str, Any]]:
        assert start_slot >= 0 and end_slot >= start_slot, "Invalid slot range"
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return []
        results = []
        for block, info in index_data["blocks"].items():
            slot = info.get("slot", 0)
            if start_slot <= slot <= end_slot:
                blk = self.storage.load_block(block)
                if blk:
                    results.append(blk)
        results.sort(key=lambda x: x.get("slot", 0))
        return results

    def search_blocks(self, query: str) -> List[Dict[str, Any]]:
        assert query, "Search query required"
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return []
        q = query.lower()
        matches = []
        for block, info in index_data["blocks"].items():
            if (q in block.lower()
                or q in str(info.get("height", "")).lower()
                or q in str(info.get("slot", "")).lower()
                or q in info.get("block_type", "").lower()):
                blk = self.storage.load_block(block)
                if blk:
                    matches.append(blk)
        matches.sort(key=lambda x: x.get("height", 0))
        return matches

    def list_blocks(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        assert limit > 0 and offset >= 0, "Invalid pagination"
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return []
        items = [(info.get("height", 0), block) for block, info in index_data["blocks"].items()]
        items.sort(key=lambda x: x[0])
        slice_ = items[offset:offset + limit]
        blocks = []
        for height, block in slice_:
            blk = self.storage.load_block(block)
            if blk:
                blocks.append(blk)
        return blocks

    # =================== CHAIN STATE & TRIE OPS ===================

    def get_chain_tip(self) -> Optional[Dict[str, Any]]:
        chain_state = self.storage.load_chain_state()
        if not chain_state or not chain_state.get("chain_tip_hash"):
            return None
        return self.storage.load_block(chain_state["chain_tip_hash"])

    def get_chain_height(self) -> int:
        cs = self.storage.load_chain_state()
        if not cs:
            return -1
        return cs.get("chain_height", -1)

    def get_finalized_block(self) -> Optional[Dict[str, Any]]:
        cs = self.storage.load_chain_state()
        if not cs or not cs.get("finalized_hash"):
            return None
        return self.storage.load_block(cs["finalized_hash"])

    def get_justified_block(self) -> Optional[Dict[str, Any]]:
        cs = self.storage.load_chain_state()
        if not cs or not cs.get("justified_hash"):
            return None
        return self.storage.load_block(cs["justified_hash"])

    def get_safe_block(self) -> Optional[Dict[str, Any]]:
        cs = self.storage.load_chain_state()
        if not cs or not cs.get("safe_hash"):
            return None
        return self.storage.load_block(cs["safe_hash"])

    def update_chain_state(self, updates: Dict[str, Any]) -> bool:
        assert isinstance(updates, dict), "Updates must be dictionary"
        def apply_updates(state):
            state.update(updates)
            state["last_updated"] = datetime.now().timestamp()
            return state
        updated = self.storage.update_chain_state(apply_updates)
        return updated is not None

    def set_chain_tip(self, block_hash: str, height: int) -> bool:
        """Atomically sets the chain tip hash and height."""
        updates = {
            'chain_tip_hash': block_hash,
            'chain_height': height,
        }
        return self.update_chain_state(updates)

    def save_transaction_trie(self, block_hash: str, tx_trie_root: str, transactions: List[Dict[str, Any]]) -> bool:
        assert block_hash and tx_trie_root
        return self.storage.save_transaction_trie_root(block_hash, tx_trie_root, transactions)

    def get_transaction_trie(self, tx_trie_root: str) -> Optional[Dict[str, Any]]:
        assert tx_trie_root
        return self.storage.load_transaction_trie_root(tx_trie_root)

    def save_receipt_trie(self, block_hash: str, receipt_trie_root: str, receipts: List[Dict[str, Any]]) -> bool:
        assert block_hash and receipt_trie_root
        return self.storage.save_receipt_trie_root(block_hash, receipt_trie_root, receipts)

    def get_receipt_trie(self, receipt_trie_root: str) -> Optional[Dict[str, Any]]:
        assert receipt_trie_root
        return self.storage.load_receipt_trie_root(receipt_trie_root)

    def save_state_trie(self, block_hash: str, state_root: str, state_data: Dict[str, Any],
                       verkle_proof: Optional[bytes] = None) -> bool:
        assert block_hash and state_root
        return self.storage.save_state_trie_root(block_hash, state_root, state_data, verkle_proof)

    def get_state_trie(self, state_root: str) -> Optional[Dict[str, Any]]:
        assert state_root
        return self.storage.load_state_trie_root(state_root)

    def save_verkle_proof(self, proof_id: str, proof_data: bytes, metadata: Dict[str, Any] = None) -> bool:
        assert proof_id and isinstance(proof_data, (bytes, bytearray))
        return self.storage.save_verkle_proof(proof_id, proof_data, metadata)

    def get_verkle_proof(self, proof_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        assert proof_id
        return self.storage.load_verkle_proof(proof_id)

    # =================== NEW METHOD FOR ACCOUNT STATE ===================
    def get_nonce_and_balance(self, address: str) -> Dict[str, Any]:
        """
        Retrieves the canonical account state (nonce, balance) for a given address
        from the latest finalized or chain tip block's state trie.
        Returns {"nonce": 0, "balance": 0.0} if account not found or no blocks exist.
        """
        target_block = self.get_finalized_block()
        if not target_block:
            target_block = self.get_chain_tip()
        
        if not target_block:
            return {"nonce": 0, "balance": 0.0} # No blocks, so no state yet

        state_root = target_block.get("state_root")
        if not state_root:
            return {"nonce": 0, "balance": 0.0} # Block has no state root

        state_trie = self.get_state_trie(state_root)
        if not state_trie:
            return {"nonce": 0, "balance": 0.0} # No state trie found for this root

        # The state_trie is expected to be a dictionary where keys are addresses
        # and values are account states (e.g., {"nonce": N, "balance": B})
        account_data = state_trie.get(address)
        if account_data:
            return {
                "nonce": account_data.get("nonce", 0),
                "balance": account_data.get("balance", 0.0)
            }
        
        return {"nonce": 0, "balance": 0.0} # Account not found in state trie

    # =================== STATISTICS & MAINTENANCE ===================

    def get_index_statistics(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return {
                "total_blocks": 0,
                "by_status": {},
                "by_consensus": {},
                "trie_stats": {"merkle": 0, "verkle": 0},
                "height_range": {"min": None, "max": None},
                "slot_range": {"min": None, "max": None}
            }
        blocks = index_data["blocks"]
        stats = {
            "total_blocks": len(blocks),
            "by_status": {},
            "by_consensus": {},
            "trie_stats": {"merkle": 0, "verkle": 0},
            "total_transactions": 0,
            "total_gas_used": 0,
            "height_range": {"min": None, "max": None},
            "slot_range": {"min": None, "max": None}
        }

        heights, slots = [], []
        for _, info in blocks.items():
            status = info.get("status", "unknown")
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

            consensus = info.get("consensus_type", "unknown")
            stats["by_consensus"][consensus] = stats["by_consensus"].get(consensus, 0) + 1

            stats["total_transactions"] += info.get("transaction_count", 0)
            stats["total_gas_used"] += info.get("gas_used", 0)

            h = info.get("height")
            if h is not None:
                heights.append(h)
            s = info.get("slot")
            if s is not None:
                slots.append(s)

        if heights:
            stats["height_range"]["min"] = min(heights)
            stats["height_range"]["max"] = max(heights)
        if slots:
            stats["slot_range"]["min"] = min(slots)
            stats["slot_range"]["max"] = max(slots)

        storage_stats = self.storage.get_storage_stats()
        stats["trie_stats"]["merkle"] = storage_stats.get("transaction_trie_count", 0) + storage_stats.get("receipt_trie_count", 0)
        stats["trie_stats"]["verkle"] = storage_stats.get("state_trie_count", 0)

        return stats

    def rebuild_index(self) -> Dict[str, Any]:
        """Rebuild index from all block records"""
        # Get all existing block hashes
        block_hashes = self.storage.list_blocks()

        rebuilt_index = {"blocks": {}}
        rebuilt_count = 0

        for block_hash in block_hashes:
            block_data = self.storage.load_block(block_hash)
            if block_data and "block_hash" in block_data:
                index_entry = self._create_index_entry_data(block_data)
                rebuilt_index["blocks"][block_hash] = index_entry
                rebuilt_count += 1

        # Save rebuilt index
        success = self.storage.save_index_data(rebuilt_index)

        return {
            "success": success,
            "blocks_indexed": rebuilt_count,
            "total_found": len(block_hashes)
        }

    def cleanup_orphaned_entries(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data()
        if not index_data or "blocks" not in index_data:
            return {"success": True, "cleaned": 0}
        valid = {}
        cleaned = 0
        for block, info in index_data["blocks"].items():
            if self.storage.block_exists(block):
                valid[block] = info
            else:
                cleaned += 1
        cleaned_index = {"blocks": valid}
        success = self.storage.save_index_data(cleaned_index)
        return {"success": success, "cleaned": cleaned, "remaining": len(valid)}

    # =================== PRIVATE HELPERS ===================

    def _create_index_entry(self, block_data: Dict[str, Any]) -> bool:
        """Create index entry for block (delegates to helper builder)."""
        entry = build_index_entry_from_block(block_data)

        def add_entry(index_data):
            index_data.setdefault("blocks", {})[block_data["block_hash"]] = entry
            return index_data

        return self.storage.update_index_data(add_entry) is not None

    def _update_index_entry(self, block_hash: str, changes: Dict[str, Any]) -> bool:
        def update_entry(index_data):
            index_data.setdefault("blocks", {})
            if block_hash not in index_data["blocks"]:
                return index_data
            for f, v in changes.items():
                if f != "block_hash":
                    index_data["blocks"][block_hash][f] = v
            return index_data
        return self.storage.update_index_data(update_entry) is not None

    def _remove_index_entry(self, block_hash: str) -> bool:
        def remove_entry(index_data):
            index_data.get("blocks", {}).pop(block_hash, None)
            return index_data
        return self.storage.update_index_data(remove_entry) is not None

    def _get_canonical_block_hash_by_height(self, height: int) -> Optional[str]:
        """
        Finds the canonical block hash for a given height by walking backwards
        from the current chain tip.
        """
        current_block = self.get_chain_tip()
        if not current_block:
            return None

        current_height = current_block.get("height")
        if height > current_height:
            return None  # Requested height is in the future

        # Walk backwards from the tip until we find the target height
        while current_block and current_block.get("height") != height:
            parent_hash = current_block.get("parent_hash")
            if not parent_hash or parent_hash == "0x" + "0" * 64:
                return None # Reached genesis without finding the height
            current_block = self.get_block(parent_hash)

        return current_block.get("block_hash") if current_block else None

    @staticmethod
    def _get_default_value(field: str) -> Any:
        return get_default_for_index_field(field)

    def close(self) -> None:
        """Close storage connections"""
        self.storage.close()
