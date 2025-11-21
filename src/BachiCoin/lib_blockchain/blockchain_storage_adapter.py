#!/usr/bin/env python3
# blockchain_adapter_eth.py - - Provides a backend-agnostic storage adapter with hybrid Merkle/Verkle support

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from BachiCoin.lib_storage.base_provider import StorageProvider
from BachiCoin.lib_blockchain.blockchain_config import BLOCKCHAIN_INDEX_KEY, get_initial_index_structure


class StorageType(Enum):
    """Storage type enumeration for hybrid Merkle/Verkle architecture"""
    BLOCK = "block"
    TRANSACTION_TRIE = "tx_trie"  # Merkle - immutable, append-only
    RECEIPT_TRIE = "receipt_trie"  # Merkle - small, non-updated blobs
    STATE_TRIE = "state_trie"  # Verkle - huge, constantly updated
    VALIDATOR_SET = "validator_set"
    ATTESTATION = "attestation"
    SYNC_COMMITTEE = "sync_committee"


@dataclass
class StateTransition:
    """State transition data for Verkle trees"""
    block_hash: str
    state_root_before: str
    state_root_after: str
    state_diff: Dict[str, Any]
    verkle_proof: Optional[bytes] = None


class BlockchainStorageAdapter:
    """Pluggable storage adapter with hybrid Merkle/Verkle support"""

    def __init__(self, provider: StorageProvider):
        self.provider = provider
        self._initialize_storage_namespaces()

    def _initialize_storage_namespaces(self):
        """Initialize storage namespaces for hybrid Merkle/Verkle architecture"""
        # Hybrid storage: Merkle for immutable data, Verkle for state
        self._namespaces = {
            StorageType.BLOCK: "blocks:",
            StorageType.TRANSACTION_TRIE: "tx_merkle:",
            StorageType.RECEIPT_TRIE: "receipt_merkle:",
            StorageType.STATE_TRIE: "state_verkle:",
            StorageType.VALIDATOR_SET: "validators:",
            StorageType.ATTESTATION: "attestations:",
            StorageType.SYNC_COMMITTEE: "sync_committee:"
        }

    def _get_storage_key(self, storage_type: StorageType, key: str) -> str:
        """Generate namespaced storage key"""
        namespace = self._namespaces.get(storage_type, "")
        return f"{namespace}{key}"

    # =================== CORE BLOCK OPERATIONS ===================

    def save_block(self, block_hash: str, block_data: Dict[str, Any]) -> bool:
        """Save block data with ETH validation"""
        assert block_hash, "Block hash cannot be empty"
        assert isinstance(block_data, dict), "Block data must be dictionary"
        assert "block_hash" in block_data, "Block data must contain block_hash"
        assert block_data["block_hash"] == block_hash, "Block hash mismatch"

        storage_key = self._get_storage_key(StorageType.BLOCK, block_hash)
        return self.provider.save(storage_key, block_data)

    def load_block(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """Load block data"""
        assert block_hash, "Block hash cannot be empty"

        storage_key = self._get_storage_key(StorageType.BLOCK, block_hash)
        return self.provider.load(storage_key)

    def delete_block(self, block_hash: str) -> bool:
        """Delete block data"""
        assert block_hash, "Block hash cannot be empty"

        storage_key = self._get_storage_key(StorageType.BLOCK, block_hash)
        return self.provider.delete(storage_key)

    def block_exists(self, block_hash: str) -> bool:
        """Check if block exists"""
        assert block_hash, "Block hash cannot be empty"

        storage_key = self._get_storage_key(StorageType.BLOCK, block_hash)
        return self.provider.exists(storage_key)

    def update_block(self, block_hash: str, update_func) -> Optional[Dict[str, Any]]:
        """Update block data using function"""
        assert block_hash, "Block hash cannot be empty"
        assert callable(update_func), "Update function must be callable"

        storage_key = self._get_storage_key(StorageType.BLOCK, block_hash)
        return self.provider.update(storage_key, update_func)

    def list_blocks(self) -> List[str]:
        """List all block hashes"""
        # Get all keys with block namespace prefix
        namespace = self._namespaces[StorageType.BLOCK]
        all_keys = self.provider.list_keys()
        block_keys = [key for key in all_keys if key.startswith(namespace)]
        # Remove namespace prefix to get actual block hashes
        return [key[len(namespace):] for key in block_keys]

    # =================== HYBRID MERKLE/VERKLE OPERATIONS ===================

    def save_transaction_trie_root(self, block_hash: str, tx_trie_root: str,
                                   tx_data: List[Dict[str, Any]]) -> bool:
        """Save transaction trie root (Merkle - immutable, append-only)"""
        assert block_hash, "Block hash cannot be empty"
        assert tx_trie_root, "Transaction trie root cannot be empty"

        tx_trie_entry = {
            "block_hash": block_hash,
            "tx_trie_root": tx_trie_root,
            "transactions": tx_data,
            "trie_type": "merkle",  # Immutable, append-only - perfect for Merkle
            "tx_count": len(tx_data)
        }

        storage_key = self._get_storage_key(StorageType.TRANSACTION_TRIE, tx_trie_root)
        return self.provider.save(storage_key, tx_trie_entry)

    def load_transaction_trie_root(self, tx_trie_root: str) -> Optional[Dict[str, Any]]:
        """Load transaction trie data (Merkle)"""
        assert tx_trie_root, "Transaction trie root cannot be empty"

        storage_key = self._get_storage_key(StorageType.TRANSACTION_TRIE, tx_trie_root)
        return self.provider.load(storage_key)

    def save_receipt_trie_root(self, block_hash: str, receipt_trie_root: str,
                               receipt_data: List[Dict[str, Any]]) -> bool:
        """Save receipt trie root (Merkle - small, non-updated blobs)"""
        assert block_hash, "Block hash cannot be empty"
        assert receipt_trie_root, "Receipt trie root cannot be empty"

        receipt_trie_entry = {
            "block_hash": block_hash,
            "receipt_trie_root": receipt_trie_root,
            "receipts": receipt_data,
            "trie_type": "merkle",  # Small blobs, non-updated - perfect for Merkle
            "receipt_count": len(receipt_data)
        }

        storage_key = self._get_storage_key(StorageType.RECEIPT_TRIE, receipt_trie_root)
        return self.provider.save(storage_key, receipt_trie_entry)

    def load_receipt_trie_root(self, receipt_trie_root: str) -> Optional[Dict[str, Any]]:
        """Load receipt trie data (Merkle)"""
        assert receipt_trie_root, "Receipt trie root cannot be empty"

        storage_key = self._get_storage_key(StorageType.RECEIPT_TRIE, receipt_trie_root)
        return self.provider.load(storage_key)

    def save_state_trie_root(self, block_hash: str, state_root: str,
                             state_data: Dict[str, Any], verkle_proof: Optional[bytes] = None) -> bool:
        """Save state trie root (Verkle - huge, constantly updated)"""
        assert block_hash, "Block hash cannot be empty"
        assert state_root, "State root cannot be empty"

        state_trie_entry = {
            "block_hash": block_hash,
            "state_root": state_root,
            "state_data": state_data,
            "trie_type": "verkle",  # Huge and constantly updated - benefits from Verkle
            "verkle_proof": verkle_proof.hex() if verkle_proof else None,
            "account_count": state_data.get("account_count", 0),
            "storage_updates": state_data.get("storage_updates", 0)
        }

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, state_root)
        return self.provider.save(storage_key, state_trie_entry)

    def load_state_trie_root(self, state_root: str) -> Optional[Dict[str, Any]]:
        """Load state trie data (Verkle)"""
        assert state_root, "State root cannot be empty"

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, state_root)
        return self.provider.load(storage_key)

    def save_state_transition(self, transition: StateTransition) -> bool:
        """Save state transition for Verkle state trie"""
        assert transition.block_hash, "Block hash required for state transition"
        assert transition.state_root_after, "New state root required"

        transition_data = {
            "block_hash": transition.block_hash,
            "state_root_before": transition.state_root_before,
            "state_root_after": transition.state_root_after,
            "state_diff": transition.state_diff,
            "verkle_proof": transition.verkle_proof.hex() if transition.verkle_proof else None,
            "trie_type": "verkle"  # State transitions use Verkle for efficiency
        }

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, f"transition_{transition.block_hash}")
        return self.provider.save(storage_key, transition_data)

    def load_state_transition(self, block_hash: str) -> Optional[StateTransition]:
        """Load state transition data"""
        assert block_hash, "Block hash cannot be empty"

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, f"transition_{block_hash}")
        data = self.provider.load(storage_key)

        if not data:
            return None

        return StateTransition(
            block_hash=data["block_hash"],
            state_root_before=data["state_root_before"],
            state_root_after=data["state_root_after"],
            state_diff=data["state_diff"],
            verkle_proof=bytes.fromhex(data["verkle_proof"]) if data["verkle_proof"] else None
        )

    # =================== VERKLE PROOF OPERATIONS (for State Trie only) ===================

    def save_verkle_proof(self, proof_id: str, proof_data: bytes, metadata: Dict[str, Any] = None) -> bool:
        """Save Verkle tree proof (used only for state trie in hybrid architecture)"""
        assert proof_id, "Proof ID cannot be empty"
        assert isinstance(proof_data, bytes), "Proof data must be bytes"

        verkle_entry = {
            "proof_id": proof_id,
            "proof_data": proof_data.hex(),
            "metadata": metadata or {},
            "proof_type": "verkle",
            "usage": "state_trie_only"  # Only state trie uses Verkle in hybrid model
        }

        # Store with state trie namespace since Verkle is only used for state
        storage_key = self._get_storage_key(StorageType.STATE_TRIE, f"proof_{proof_id}")
        return self.provider.save(storage_key, verkle_entry)

    def load_verkle_proof(self, proof_id: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        """Load Verkle tree proof (state trie only)"""
        assert proof_id, "Proof ID cannot be empty"

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, f"proof_{proof_id}")
        data = self.provider.load(storage_key)

        if not data:
            return None

        proof_data = bytes.fromhex(data["proof_data"])
        metadata = data.get("metadata", {})
        return proof_data, metadata

    def delete_verkle_proof(self, proof_id: str) -> bool:
        """Delete Verkle proof (state trie only)"""
        assert proof_id, "Proof ID cannot be empty"

        storage_key = self._get_storage_key(StorageType.STATE_TRIE, f"proof_{proof_id}")
        return self.provider.delete(storage_key)

    # =================== PoS VALIDATOR OPERATIONS ===================

    def save_validator_set(self, epoch: int, validator_data: Dict[str, Any]) -> bool:
        """Save validator set for PoS"""
        assert epoch >= 0, "Epoch must be non-negative"
        assert isinstance(validator_data, dict), "Validator data must be dictionary"

        validator_entry = {
            "epoch": epoch,
            "validators": validator_data,
            "consensus_type": "proof_of_stake"
        }

        storage_key = self._get_storage_key(StorageType.VALIDATOR_SET, f"epoch_{epoch}")
        return self.provider.save(storage_key, validator_entry)

    def load_validator_set(self, epoch: int) -> Optional[Dict[str, Any]]:
        """Load validator set for epoch"""
        assert epoch >= 0, "Epoch must be non-negative"

        storage_key = self._get_storage_key(StorageType.VALIDATOR_SET, f"epoch_{epoch}")
        return self.provider.load(storage_key)

    def save_attestation(self, slot: int, attestation_data: Dict[str, Any]) -> bool:
        """Save PoS attestation"""
        assert slot >= 0, "Slot must be non-negative"
        assert isinstance(attestation_data, dict), "Attestation data must be dictionary"

        attestation_entry = {
            "slot": slot,
            "attestation": attestation_data,
            "consensus_type": "proof_of_stake"
        }

        storage_key = self._get_storage_key(StorageType.ATTESTATION, f"slot_{slot}")
        return self.provider.save(storage_key, attestation_entry)

    def load_attestations_for_slot(self, slot: int) -> List[Dict[str, Any]]:
        """Load all attestations for a slot"""
        assert slot >= 0, "Slot must be non-negative"

        storage_key = self._get_storage_key(StorageType.ATTESTATION, f"slot_{slot}")
        data = self.provider.load(storage_key)

        if not data:
            return []

        return [data]  # Simplified - in practice might need range queries

    # =================== SYNC COMMITTEE OPERATIONS ===================

    def save_sync_committee(self, period: int, committee_data: Dict[str, Any]) -> bool:
        """Save sync committee for light client support"""
        assert period >= 0, "Period must be non-negative"
        assert isinstance(committee_data, dict), "Committee data must be dictionary"

        committee_entry = {
            "period": period,
            "committee": committee_data,
            "sync_type": "altair"  # ETH upgrade that introduced sync committees
        }

        storage_key = self._get_storage_key(StorageType.SYNC_COMMITTEE, f"period_{period}")
        return self.provider.save(storage_key, committee_entry)

    def load_sync_committee(self, period: int) -> Optional[Dict[str, Any]]:
        """Load sync committee for period"""
        assert period >= 0, "Period must be non-negative"

        storage_key = self._get_storage_key(StorageType.SYNC_COMMITTEE, f"period_{period}")
        return self.provider.load(storage_key)

    # =================== INDEX OPERATIONS (ETH-aligned) ===================

    # In lib_blockchain/blockchain_storage_adapter.py

    def save_index_data(self, index_data: Dict[str, Any]) -> bool:
        """Save blockchain index data"""
        assert isinstance(index_data, dict), "Index data must be dictionary"
        return self.provider.save(BLOCKCHAIN_INDEX_KEY, index_data)

    def load_index_data(self) -> Optional[Dict[str, Any]]:
        """Load blockchain index data"""
        data = self.provider.load(BLOCKCHAIN_INDEX_KEY)
        return data

    def ensure_index_exists(self) -> bool:
        """Ensures the index file exists and contains the essential 'chain_state' key."""
        index_data = self.load_index_data()

        if not index_data or "chain_state" not in index_data:
            initial_data = get_initial_index_structure()
            return self.save_index_data(initial_data)

        return True

    def update_index_data(self, update_func) -> Optional[Dict[str, Any]]:
        """Update index data using function"""
        assert callable(update_func), "Update function must be callable"
        return self.provider.update(BLOCKCHAIN_INDEX_KEY, update_func)

    # =================== CHAIN STATE OPERATIONS ===================

    def save_chain_state(self, state_data: Dict[str, Any]) -> bool:
        """Save blockchain state"""
        assert isinstance(state_data, dict), "State data must be dictionary"

        # ETH-aligned state structure
        eth_state = {
            "chain_tip_hash": state_data.get("chain_tip_hash"),
            "chain_height": state_data.get("chain_height", 0),
            "finalized_hash": state_data.get("finalized_hash"),
            "finalized_height": state_data.get("finalized_height", 0),
            "safe_hash": state_data.get("safe_hash"),
            "safe_height": state_data.get("safe_height", 0),
            "state_root": state_data.get("state_root"),
            "consensus_type": state_data.get("consensus_type", "proof_of_work"),
            "network": state_data.get("network", "mainnet"),
            "last_updated": state_data.get("last_updated")
        }

        return self.provider.save("__blockchain_state__", eth_state)

    def load_chain_state(self) -> Optional[Dict[str, Any]]:
        """Load blockchain state"""
        index_data = self.load_index_data()
        return index_data.get("chain_state") if index_data else None

    def update_chain_state(self, update_func) -> Optional[Dict[str, Any]]:
        """Update chain state using function that receives and returns the chain_state dict."""
        assert callable(update_func), "Update function must be callable"

        def update_index_with_chain_state(index_data: Dict[str, Any]) -> Dict[str, Any]:
            # The update_func operates on the chain_state dictionary
            current_chain_state = index_data.get("chain_state", {})
            index_data["chain_state"] = update_func(current_chain_state)
            return index_data

        return self.update_index_data(update_index_with_chain_state)

    # =================== UTILITY OPERATIONS ===================

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics by type"""
        all_keys = self.provider.list_keys()
        stats = {"total_keys": len(all_keys)}

        for storage_type, namespace in self._namespaces.items():
            type_keys = [key for key in all_keys if key.startswith(namespace)]
            stats[f"{storage_type.value}_count"] = len(type_keys)

        return stats

    def close(self) -> None:
        """Close storage connection"""
        self.provider.close()


if __name__ == "__main__":
    from BachiCoin.lib_blockchain.blockchain_storage_factory import BlockchainStorageFactory
    from tests.test_config import dirs
    import time

    print("=== BlockchainStorageAdapter Test ===")

    # Create adapter and ensure index exists
    adapter = BlockchainStorageFactory.create_blockchain_storage(dirs)
    print(f"{adapter}\nwill store data at {dirs.blockchain}")

    # Generate test data
    block_hash = "0x" + "a" * 64
    print(f"Test block hash: {block_hash}")

    # Test ETH-aligned block data
    test_block_data = {
        "block_hash": block_hash,
        "parent_hash": "0x" + "0" * 64,
        "height": 1,
        "timestamp": int(time.time()),
        "transactions": ["0x1111", "0x2222"],
        "transaction_count": 2,
        "gas_limit": 15000000,
        "gas_used": 10000000,
        "base_fee_per_gas": 20000000000,  # 20 gwei
        "state_root": "0x" + "b" * 64,
        "consensus_type": "proof_of_work",
        "status": "valid"
    }

    # Test basic block operations
    print(f"✅ Save block: {adapter.save_block(block_hash, test_block_data)}")
    print(f"✅ Block exists: {adapter.block_exists(block_hash)}")

    loaded = adapter.load_block(block_hash)
    if loaded:
        print(f"✅ Load block: Height {loaded['height']}, Status: {loaded['status']}")
        print(f"   Gas used: {loaded['gas_used']:,}, Base fee: {loaded['base_fee_per_gas']:,}")
    else:
        print("❌ Failed to load block")

    # Test setting the chain state, which is critical for get_chain_tip
    def set_tip_func(index_data: Dict[str, Any]) -> Dict[str, Any]:
        # The index_data now has a top-level 'chain_state' key from the factory
        chain_state = index_data.get("chain_state", {})
        chain_state["chain_tip_hash"] = block_hash
        chain_state["chain_height"] = 1
        index_data["chain_state"] = chain_state
        return index_data

    result = adapter.update_index_data(set_tip_func)
    print(f"✅ Chain tip state in index -> {result.get('chain_state')}")

    # Test transaction trie (Merkle - immutable, append-only)
    tx_trie_root = "0x" + "d" * 64
    tx_data = [
        {"tx_hash": "0x1111", "tx_type": "transfer", "amount": 100},
        {"tx_hash": "0x2222", "tx_type": "transfer", "amount": 50}
    ]

    print(f"✅ Save tx trie (Merkle): {adapter.save_transaction_trie_root(block_hash, tx_trie_root, tx_data)}")

    loaded_tx_trie = adapter.load_transaction_trie_root(tx_trie_root)
    if loaded_tx_trie:
        print(f"✅ Load tx trie: {loaded_tx_trie['tx_count']} txs, Type: {loaded_tx_trie['trie_type']}")

    # Test receipt trie (Merkle - small, non-updated blobs)
    receipt_trie_root = "0x" + "e" * 64
    receipt_data = [
        {"tx_hash": "0x1111", "gas_used": 21000, "status": 1},
        {"tx_hash": "0x2222", "gas_used": 21000, "status": 1}
    ]
    print(
        f"✅ Save receipt trie (Merkle): {adapter.save_receipt_trie_root(block_hash, receipt_trie_root, receipt_data)}")
    loaded_receipt_trie = adapter.load_receipt_trie_root(receipt_trie_root)
    if loaded_receipt_trie:
        print(
            f"✅ Load receipt trie: {loaded_receipt_trie['receipt_count']} receipts, Type: {loaded_receipt_trie['trie_type']}")

    # Test state trie (Verkle - huge, constantly updated)
    state_root = "0x" + "f" * 64
    state_data = {
        "account_count": 1000000,  # Huge
        "storage_updates": 50000,  # Constantly updated
        "total_balance": 21000000
    }
    verkle_proof = b"verkle_state_proof_compressed"
    print(
        f"✅ Save state trie (Verkle): {adapter.save_state_trie_root(block_hash, state_root, state_data, verkle_proof)}")

    loaded_state_trie = adapter.load_state_trie_root(state_root)
    if loaded_state_trie:
        print(
            f"✅ Load state trie: {loaded_state_trie['account_count']:,} accounts, Type: {loaded_state_trie['trie_type']}")
        print(f"   Storage updates: {loaded_state_trie['storage_updates']:,}")

    # Test Verkle operations (state trie only)
    proof_data = b"verkle_proof_state_only"
    proof_metadata = {"block_height": 1, "proof_type": "state_transition", "usage": "state_trie"}

    print(f"✅ Save Verkle proof (state only): {adapter.save_verkle_proof('state_proof_1', proof_data, proof_metadata)}")

    loaded_proof = adapter.load_verkle_proof('state_proof_1')
    if loaded_proof:
        proof_bytes, metadata = loaded_proof
        print(f"✅ Load Verkle proof: {len(proof_bytes)} bytes, Usage: {metadata['usage']}")

    # Test storage statistics
    stats = adapter.get_storage_stats()
    print(f"✅ Storage stats: {stats['total_keys']} total keys")
    print(f"   Blocks: {stats.get('block_count', 0)}")
    print(f"   Tx tries (Merkle): {stats.get('transaction_trie_count', 0)}")
    print(f"   Receipt tries (Merkle): {stats.get('receipt_trie_count', 0)}")
    print(f"   State tries (Verkle): {stats.get('state_trie_count', 0)}")

    adapter.close()
    print(f"✅ ETH-aligned storage adapter test complete!")
    print(f"🔗 Ready for hybrid Merkle/Verkle blockchain!")
    print(f"📊 Tx/Receipt: Merkle (immutable) | State: Verkle (huge, updated)")
    print(f"⚡ PoS storage patterns prepared!")
