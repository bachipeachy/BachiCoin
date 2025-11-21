#!/usr/bin/env python3
"""blockchain.py - ETH-aligned pure chain utilities with hybrid Merkle/Verkle support (CONSENSUS CLEANED)"""

from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum

from BachiCoin.lib_blockchain.blockchain_config import BlockchainConfig
from BachiCoin.lib_blockchain.blockchain_validation import get_validation_errors
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService


class ChainReorgReason(Enum):
    """Reasons for chain reorganization (NON-CONSENSUS)"""
    HIGHER_DIFFICULTY = "higher_difficulty"  # LEGACY - FOR POW COMPATIBILITY
    HIGHER_WEIGHT = "higher_weight"          # LEGACY - FOR POS COMPATIBILITY
    FINALITY_CONFLICT = "finality_conflict"  # CONSENSUS MODULE WILL HANDLE


class Blockchain:
    """ETH-aligned blockchain utilities - pure functions only"""
    # =================== CHAIN TRAVERSAL UTILITIES ===================

    @staticmethod
    def find_common_ancestor(chain1_hashes: List[str], chain2_hashes: List[str]) -> Optional[str]:
        """Find common ancestor between two chains (fork point detection)"""
        assert isinstance(chain1_hashes, list), "Chain 1 must be list of hashes"
        assert isinstance(chain2_hashes, list), "Chain 2 must be list of hashes"
        
        set1 = set(chain1_hashes)
        for block_hash in chain2_hashes:
            if block_hash in set1:
                return block_hash
        return None

    @staticmethod
    def get_chain_to_genesis(start_hash: str, blockchain_service: BlockchainIndexService) -> List[str]:
        """Get chain of block hashes from start to genesis"""
        assert start_hash, "Start hash cannot be empty"
        assert blockchain_service, "Blockchain service required"
        
        chain = []
        current_hash = start_hash
        genesis_hash = "0x" + "0" * 64

        while current_hash and current_hash != genesis_hash:
            chain.append(current_hash)
            block_data = blockchain_service.storage.load_block(current_hash)
            if not block_data:
                break
            current_hash = block_data.get("parent_hash")

        return chain

    @staticmethod
    def get_chain_between_blocks(start_hash: str, end_hash: str, blockchain_service: BlockchainIndexService) -> List[str]:
        """Get chain of block hashes between two blocks (inclusive)"""
        assert start_hash, "Start hash cannot be empty"
        assert end_hash, "End hash cannot be empty"
        assert blockchain_service, "Blockchain service required"
        
        chain = []
        current_hash = start_hash
        
        while current_hash and current_hash != end_hash:
            chain.append(current_hash)
            block_data = blockchain_service.storage.load_block(current_hash)
            if not block_data:
                break
            current_hash = block_data.get("parent_hash")
        
        if current_hash == end_hash:
            chain.append(end_hash)
            
        return chain

    # =================== CHAIN COMPARISON  ===================

    @staticmethod
    def compare_chain_metrics(new_chain_info: Dict[str, Any], current_chain_info: Dict[str, Any]) -> Dict[str, Any]:
        """Compare chain metrics"""
        assert isinstance(new_chain_info, dict), "New chain info must be dictionary"
        assert isinstance(current_chain_info, dict), "Current chain info must be dictionary"
        
        # Return raw metrics for consensus module to evaluate
        return {
            "new_height": new_chain_info.get("height", 0),
            "current_height": current_chain_info.get("height", 0),
            "new_total_difficulty": new_chain_info.get("total_difficulty", 0),  # LEGACY
            "current_total_difficulty": current_chain_info.get("total_difficulty", 0),  # LEGACY
            "new_weight": new_chain_info.get("chain_weight", 0),  # FOR CONSENSUS MODULE
            "current_weight": current_chain_info.get("chain_weight", 0),  # FOR CONSENSUS MODULE
            "consensus_comparison": "deferred_to_consensus_module"
        }

    @staticmethod
    def plan_chain_reorganization(old_tip_hash: str, new_tip_hash: str, blockchain_service: BlockchainIndexService) -> Dict[str, Any]:
        """Plan chain reorganization - return blocks to mark canonical/non-canonical"""
        assert old_tip_hash, "Old tip hash cannot be empty"
        assert new_tip_hash, "New tip hash cannot be empty"
        assert blockchain_service, "Blockchain service required"
        
        # Get both chains to genesis
        old_chain = Blockchain.get_chain_to_genesis(old_tip_hash, blockchain_service)
        new_chain = Blockchain.get_chain_to_genesis(new_tip_hash, blockchain_service)

        # Find fork point
        common_ancestor = Blockchain.find_common_ancestor(old_chain, new_chain)

        if not common_ancestor:
            return {
                "success": False,
                "error": "No common ancestor found",
                "common_ancestor": None,
                "blocks_to_unmark": [],
                "blocks_to_mark": []
            }

        # Blocks to mark as non-canonical (old chain after fork)
        blocks_to_unmark = []
        for block_hash in old_chain:
            if block_hash == common_ancestor:
                break
            blocks_to_unmark.append(block_hash)

        # Blocks to mark as canonical (new chain after fork)
        blocks_to_mark = []
        for block_hash in new_chain:
            if block_hash == common_ancestor:
                break
            blocks_to_mark.append(block_hash)

        return {
            "success": True,
            "common_ancestor": common_ancestor,
            "blocks_to_unmark": blocks_to_unmark,
            "blocks_to_mark": blocks_to_mark,
            "reorg_depth": len(blocks_to_unmark)
        }

    # =================== CHAIN VALIDATION UTILITIES (BASIC ONLY) ===================

    @staticmethod
    def validate_chain_structure_batch(blocks: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """Validate chain structure for multiple blocks - BASIC VALIDATION ONLY"""
        assert isinstance(blocks, list), "Blocks must be list"
        
        errors = []

        for i in range(1, len(blocks)):
            current_block = blocks[i]
            parent_block = blocks[i - 1]

            # Basic structure checks
            if current_block["parent_hash"] != parent_block["block_hash"]:
                errors.append(f"Block {current_block['height']}: Invalid parent hash")

            if current_block["height"] != parent_block["height"] + 1:
                errors.append(f"Block {current_block['height']}: Invalid height sequence")

        return len(errors) == 0, errors

    @staticmethod
    def validate_hybrid_trie_structure(block_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate hybrid Merkle/Verkle trie structure"""
        assert isinstance(block_data, dict), "Block data must be dictionary"
        
        errors = []
        
        # Validate transaction trie (should be Merkle)
        tx_trie_root = block_data.get("tx_trie_root")
        if tx_trie_root:
            # Transaction tries should use Merkle (immutable, append-only)
            if not tx_trie_root.startswith("0x"):
                errors.append("Transaction trie root must be hex string")
        
        # Validate receipt trie (should be Merkle)  
        receipt_trie_root = block_data.get("receipt_trie_root")
        if receipt_trie_root:
            # Receipt tries should use Merkle (small, non-updated blobs)
            if not receipt_trie_root.startswith("0x"):
                errors.append("Receipt trie root must be hex string")
        
        # Validate state trie (should be Verkle)
        state_root = block_data.get("state_root")
        if state_root:
            # State tries should use Verkle (huge, constantly updated)
            if not state_root.startswith("0x"):
                errors.append("State root must be hex string")
                
        return len(errors) == 0, errors

    @staticmethod
    def validate_chain_integrity(start_hash: str, blockchain_service: BlockchainIndexService, max_blocks: int = 100) -> Tuple[bool, List[str]]:
        """Validate chain integrity - BASIC STRUCTURE ONLY"""
        assert start_hash, "Start hash cannot be empty"
        assert blockchain_service, "Blockchain service required"
        assert max_blocks > 0, "Max blocks must be positive"
        
        errors = []

        # Get chain to validate
        chain_hashes = Blockchain.get_chain_to_genesis(start_hash, blockchain_service)[:max_blocks]

        # Load all blocks
        blocks = []
        for block_hash in chain_hashes:
            block_data = blockchain_service.storage.load_block(block_hash)
            if not block_data:
                errors.append(f"Block not found: {block_hash[:16]}...")
                continue
            blocks.append(block_data)

        # Validate each block (BASIC VALIDATION ONLY)
        for block_data in blocks:
            # Standard block validation
            block_errors = get_validation_errors(block_data, "validation")
            if block_errors:
                height = block_data.get("height", "unknown")
                errors.extend([f"Block {height}: {err}" for err in block_errors])
                
            # Hybrid trie structure validation
            trie_valid, trie_errors = Blockchain.validate_hybrid_trie_structure(block_data)
            if not trie_valid:
                height = block_data.get("height", "unknown")
                errors.extend([f"Block {height} trie: {err}" for err in trie_errors])

        # Validate chain structure (BASIC ONLY)
        structure_valid, structure_errors = Blockchain.validate_chain_structure_batch(blocks)
        if not structure_valid:
            errors.extend(structure_errors)

        return len(errors) == 0, errors

    # =================== UTILITY HELPER FUNCTIONS ===================

    @staticmethod
    def get_chain_statistics(chain_hashes: List[str], blockchain_service: BlockchainIndexService) -> Dict[str, Any]:
        """Get statistics for a chain segment"""
        assert isinstance(chain_hashes, list), "Chain hashes must be list"
        assert blockchain_service, "Blockchain service required"
        
        stats = {
            "block_count": len(chain_hashes),
            "total_transactions": 0,
            "total_gas_used": 0,
            "execution_states": {},  # EXECUTION STATES ONLY
            "trie_types": {"merkle": 0, "verkle": 0},
            "height_range": {"min": None, "max": None}
        }
        
        heights = []
        for block_hash in chain_hashes:
            block_data = blockchain_service.storage.load_block(block_hash)
            if not block_data:
                continue
                
            # Basic stats
            stats["total_transactions"] += len(block_data.get("transactions", []))
            stats["total_gas_used"] += block_data.get("gas_used", 0)
            
            # Execution state tracking (NON-CONSENSUS)
            execution_status = block_data.get("status", "unknown")
            stats["execution_states"][execution_status] = stats["execution_states"].get(execution_status, 0) + 1
            
            # Trie type tracking (hybrid architecture)
            if block_data.get("state_root"):
                stats["trie_types"]["verkle"] += 1  # State uses Verkle
            if block_data.get("tx_trie_root") or block_data.get("receipt_trie_root"):
                stats["trie_types"]["merkle"] += 1  # Tx/Receipt use Merkle
            
            # Height tracking
            height = block_data.get("height")
            if height is not None:
                heights.append(height)
        
        if heights:
            stats["height_range"]["min"] = min(heights)
            stats["height_range"]["max"] = max(heights)
            
        return stats

    @staticmethod
    def detect_chain_forks(blockchain_service: BlockchainIndexService, look_back_blocks: int = 100) -> List[Dict[str, Any]]:
        """Detect potential chain forks"""
        assert blockchain_service, "Blockchain service required"
        assert look_back_blocks > 0, "Look back blocks must be positive"
        
        # Get all blocks from index
        all_blocks = blockchain_service.list_blocks()
        
        # Group blocks by height to find forks
        blocks_by_height = {}
        for block_info in all_blocks:
            height = block_info.get("height")
            if height is not None:
                if height not in blocks_by_height:
                    blocks_by_height[height] = []
                blocks_by_height[height].append(block_info)
        
        # Find heights with multiple blocks (potential forks)
        forks = []
        for height, blocks in blocks_by_height.items():
            if len(blocks) > 1:
                fork_info = {
                    "height": height,
                    "fork_count": len(blocks),
                    "blocks": [{"hash": b["block_hash"], "canonical": b.get("is_canonical", False)} for b in blocks]
                }
                forks.append(fork_info)
        
        # Sort by height
        forks.sort(key=lambda x: x["height"])
        return forks

    # =================== LEGACY SUPPORT UTILITIES ===================

    @staticmethod
    def calculate_legacy_difficulty(block_data: Dict[str, Any], parent_block_data: Dict[str, Any]) -> int:
        """Calculate block difficulty for PoW compatibility"""
        assert isinstance(block_data, dict), "Block data must be dictionary"
        assert isinstance(parent_block_data, dict), "Parent block data must be dictionary"
        
        config = BlockchainConfig()
        base_difficulty = block_data.get("difficulty", config.MIN_DIFFICULTY)
        
        # Simple difficulty calculation for legacy PoW compatibility
        return base_difficulty

    @staticmethod
    def get_execution_ready_blocks(blockchain_service: BlockchainIndexService) -> List[str]:
        """Get list of blocks ready for execution"""
        assert blockchain_service, "Blockchain service required"
        
        # Get blocks that are consensus-validated but not yet executed
        all_blocks = blockchain_service.list_blocks()
        execution_ready = []
        
        for block_info in all_blocks:
            # CONSENSUS MODULE SHOULD SET consensus_status = "validated"
            consensus_status = block_info.get("consensus_status", "pending")
            execution_status = block_info.get("status", "pending")
            
            if consensus_status == "validated" and execution_status == "pending":
                execution_ready.append(block_info["block_hash"])
        
        return execution_ready


if __name__ == "__main__":
    """Test ETH-aligned blockchain utilities (consensus removed)"""
    from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
    from tests.test_config import dirs

    print("=== Blockchain Pure Utilities Test ===")
    blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(dirs)

    # Test chain info if chain exists
    chain_state = blockchain_service.storage.load_chain_state()
    if chain_state and chain_state.get("chain_tip_hash"):
        tip_hash = chain_state["chain_tip_hash"]
        height = chain_state.get("chain_height", -1)

        print(f"Found existing chain - Height: {height}, Tip: {tip_hash[:16]}...")

        # Test basic chain utilities
        print(f"\n=== Testing Basic Chain Utilities ===")

        # Test get chain to genesis
        chain_hashes = Blockchain.get_chain_to_genesis(tip_hash, blockchain_service)
        print(f"✅ Chain to genesis: {len(chain_hashes)} blocks")

        # Test hybrid trie validation
        tip_block = blockchain_service.storage.load_block(tip_hash)
        if tip_block:
            trie_valid, trie_errors = Blockchain.validate_hybrid_trie_structure(tip_block)
            print(f"✅ Hybrid trie validation: {trie_valid}")
            if trie_errors:
                for error in trie_errors[:2]:
                    print(f"   Trie error: {error}")

        # Test basic chain validation
        is_valid, errors = Blockchain.validate_chain_integrity(tip_hash, blockchain_service, max_blocks=5)
        print(f"✅ Basic chain validation: {is_valid}")
        if errors:
            for error in errors[:3]:
                print(f"   Error: {error}")

        # Test common ancestor (with itself)
        ancestor = Blockchain.find_common_ancestor(chain_hashes, chain_hashes[:2])
        print(f"✅ Common ancestor test: {ancestor[:16] if ancestor else 'None'}...")

        # Test reorganization planning (structure only)
        if len(chain_hashes) > 1:
            fake_new_tip = chain_hashes[1]  # Use older block as fake new tip  
            reorg_plan = Blockchain.plan_chain_reorganization(tip_hash, fake_new_tip, blockchain_service)
            print(f"✅ Reorganization plan: {reorg_plan['success']}, Depth: {reorg_plan.get('reorg_depth', 0)}")

        # Test chain metrics comparison (for consensus module)
        new_chain_metrics = {"height": height, "total_difficulty": 1000, "chain_weight": 500}
        current_chain_metrics = {"height": height-1, "total_difficulty": 800, "chain_weight": 400}
        metrics_comparison = Blockchain.compare_chain_metrics(new_chain_metrics, current_chain_metrics)
        print(f"✅ Chain metrics comparison: {metrics_comparison['consensus_comparison']}")

        # Test chain statistics
        stats = Blockchain.get_chain_statistics(chain_hashes[:5], blockchain_service)
        print(f"✅ Chain stats: {stats['block_count']} blocks, {stats['total_transactions']} txs")
        print(f"   Execution states: {stats['execution_states']}")
        print(f"   Trie types: {stats['trie_types']}")

        # Test fork detection
        forks = Blockchain.detect_chain_forks(blockchain_service)
        print(f"✅ Fork detection: {len(forks)} forks found")

        # Test execution-ready blocks
        execution_ready = Blockchain.get_execution_ready_blocks(blockchain_service)
        print(f"✅ Execution-ready blocks: {len(execution_ready)}")

    else:
        print("No existing chain found - create some blocks first with blockchain_builder.py")

    # Test static utilities without blockchain
    print(f"\n=== Testing Static Utilities ===")

    # Test chain metrics comparison
    chain1 = {"height": 100, "total_difficulty": 2000, "chain_weight": 1500}
    chain2 = {"height": 99, "total_difficulty": 1000, "chain_weight": 1000}
    
    comparison = Blockchain.compare_chain_metrics(chain1, chain2)
    print(f"✅ Chain comparison: Height {comparison['new_height']} vs {comparison['current_height']}")

    # Test common ancestor with dummy data
    chain1_hashes = ["0xabc", "0xdef", "0x123"]
    chain2_hashes = ["0xabc", "0x456", "0x789"]
    ancestor = Blockchain.find_common_ancestor(chain1_hashes, chain2_hashes)
    print(f"✅ Common ancestor: {ancestor}")

    # Test legacy difficulty calculation
    test_block = {"difficulty": 100}
    test_parent = {"difficulty": 90}
    legacy_difficulty = Blockchain.calculate_legacy_difficulty(test_block, test_parent)
    print(f"✅ Legacy difficulty: {legacy_difficulty}")

    blockchain_service.close()

    print(f"\n=== ETH-Aligned Pure Blockchain Chain Utilities Ready  ===")
