#!/usr/bin/env python3
"""
proposer_index_service.py – Thin orchestrator for proposer duties.
"""

import time
from typing import Dict, Any, Optional, List, Callable # Added Callable
from datetime import datetime
from BachiCoin.lib_proposer import proposer_helper
from BachiCoin.lib_proposer.proposer_config import (
    ProposerConfig,
    ProposerStatus,
    is_valid_proposer_status,
)
from BachiCoin.lib_proposer.proposer_validation import (
    assert_valid_for_creation,
    assert_valid_for_update,
    validate_candidate_block,
)
from BachiCoin.lib_proposer.proposer_storage_adapter import ProposerStorageAdapter

# Direct imports for dependent services
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService # Direct import
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService # Direct import
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService # Direct import

from BachiCoin.lib_blockchain.blockchain_config import (
    calculate_next_base_fee,
    BlockchainConfig,
    ConsensusType,
    NetworkType,
)
from BachiCoin.lib_consensus.consensus_config import SLOTS_PER_EPOCH


class ProposerIndexService:
    """Service to manage proposal duties and build candidate blocks."""

    def __init__(
        self,
        storage_adapter: ProposerStorageAdapter,
        validator_index_service: ValidatorIndexService, # Direct import
        mempool_index_service: MempoolIndexService, # Direct import
        blockchain_index_service: BlockchainIndexService # Direct import
    ):
        """Initializes the service with all dependencies injected."""
        self.storage = storage_adapter
        self.validator_index_service = validator_index_service
        self.mempool_index_service = mempool_index_service
        self.blockchain_index_service = blockchain_index_service
        self.config = ProposerConfig()
        self.blockchain_config = BlockchainConfig()

    def _add_duty_to_indices(self, proposal_data: Dict[str, Any]) -> None:
        def update_func(index_data: Dict[str, Any]) -> Dict[str, Any]:
            return proposer_helper.update_index_with_proposal(index_data, proposal_data)
        self.storage.update_proposer_index(update_func)

    def assign_proposal_duty(self, slot: int, validator_index: int) -> Optional[str]:
        """Assigns a proposal duty to a validator for a specific slot."""
        # Use direct service call
        assert self.validator_index_service.get_validator(validator_index), f"Validator {validator_index} not found."
        
        index = self.storage.load_proposer_index() or {}
        # Ensure the nested structure exists before checking it
        proposers_index = index.setdefault('proposers', {})
        duties_by_slot = proposers_index.setdefault('duties_by_slot', {})
        
        assert str(slot) not in duties_by_slot, f"Slot {slot} is already assigned."

        proposal_data = proposer_helper.create_proposal_data(slot, validator_index)
        assert_valid_for_creation(proposal_data)

        self.storage.save_proposal(proposal_data["proposal_id"], proposal_data)
        self._add_duty_to_indices(proposal_data)
        return proposal_data["proposal_id"]

    def build_candidate_block(self, slot: int) -> Optional[Dict[str, Any]]:
        """
        Builds a candidate block for a given slot. Does NOT save the block.
        This is the primary method called by the consensus orchestrator.
        """
        proposal_duty = self.get_proposal_by_slot(slot)
        if not proposal_duty:
            print(f"[Proposer] No proposal duty found for slot {slot}")
            return None

        if proposal_duty['status'] != ProposerStatus.AWAITING_DUTY.value:
            print(f"[Proposer] Duty for slot {slot} is not in an awaiting state.")
            return None

        # Use direct service call
        parent_block = self.blockchain_index_service.get_chain_tip()
        assert parent_block, "[Proposer] Could not get chain tip to build on."

        # Use direct service call
        pending_txs = self.mempool_index_service.get_pending_transactions()

        # --- Correctly populate all required fields ---
        epoch = slot // SLOTS_PER_EPOCH
        next_base_fee = calculate_next_base_fee(
            parent_block.get("header", {}).get("gas_used", 0),
            parent_block.get("header", {}).get("gas_limit", self.blockchain_config.DEFAULT_GAS_LIMIT),
            parent_block.get("header", {}).get("base_fee_per_gas", self.blockchain_config.MIN_BASE_FEE),
        )

        # Create the block with a nested header structure
        block_data = {
            "header": {
                "slot": slot,
                "epoch": epoch,
                "proposer_index": proposal_duty['validator_index'],
                "parent_hash": parent_block['block_hash'],
                "height": parent_block['height'] + 1,
                "gas_limit": parent_block.get("header", {}).get("gas_limit", self.blockchain_config.DEFAULT_GAS_LIMIT),
                "base_fee_per_gas": next_base_fee,
                "timestamp": int(time.time()),
                "extra_data": b"BachiCoin Block",
                "network": NetworkType.TESTNET.value,
                "consensus_type": ConsensusType.PROOF_OF_STAKE.value,
                "randao_reveal": "0x" + "a" * 192,  # Placeholder
            },
            "body": {
                "transactions": pending_txs,
                "attestations": [], # Placeholder for future functionality
                "deposits": [], # Placeholder for future functionality
            },
            "block_type": "regular",
        }

        # --- STAGE 1 VALIDATION ---
        # Pass callables to the pure validation function
        # Note: The validation function might need adjustment to handle the new structure
        errors = validate_candidate_block(
            block_data,
            get_validator_func=self.validator_index_service.get_validator, # Pass bound method
            get_chain_tip_func=self.blockchain_index_service.get_chain_tip # Pass bound method
        )
        if errors:
            print(f"[Proposer] Candidate block for slot {slot} failed validation:")
            for error in errors:
                print(f"  - {error}")
            return None
        # --- END STAGE 1 VALIDATION ---

        for tx in pending_txs:
            tx_hash = tx.get("tx_hash")
            if tx_hash:
                # Use direct service call
                self.mempool_index_service.remove_transaction(tx_hash)
        
        return block_data

    def update_proposal_status_after_commit(self, block_data: Dict[str, Any]) -> bool:
        """
        Updates the proposal duty status after a block has been successfully committed.
        This is called by the consensus orchestrator.
        """
        slot = block_data.get("header", {}).get("slot")
        if not slot:
            return False

        proposal_duty = self.get_proposal_by_slot(slot)
        if not proposal_duty:
            return False

        update_payload = {
            "block_hash": block_data.get("block_hash"), # Assuming block_hash is added post-commit
            "transaction_count": len(block_data.get("body", {}).get("transactions", [])),
            "payload_size_bytes": len(str(block_data.get("body", {}).get("transactions", []))),
        }
        return self.update_proposal_status(
            proposal_duty['proposal_id'],
            ProposerStatus.PROPOSAL_SUCCESS.value,
            update_payload
        )

    def update_proposal_status(self, proposal_id: str, new_status: str,
                               update_payload: Optional[Dict[str, Any]] = None) -> bool:
        """Updates the status and other metadata of a specific proposal duty."""
        assert is_valid_proposer_status(new_status), f"Invalid status: {new_status}"
        payload = update_payload or {}
        payload["status"] = new_status
        assert_valid_for_update(payload)

        def update_func(proposal_data: Dict[str, Any]) -> Dict[str, Any]:
            proposal_data.update(payload)
            proposal_data["proposed_at"] = datetime.now().isoformat() + "Z"
            return proposal_data

        updated_proposal = self.storage.update_proposal(proposal_id, update_func)
        return updated_proposal is not None

    # --- Read-only methods --- 
    def get_proposal_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_proposal(proposal_id)

    def get_proposal_by_slot(self, slot: int) -> Optional[Dict[str, Any]]:
        index = self.storage.load_proposer_index()
        pid = index.get('proposers', {}).get("duties_by_slot", {}).get(str(slot))
        return self.get_proposal_by_id(pid) if pid else None

    def get_proposals_for_epoch(self, epoch: int) -> List[Dict[str, Any]]:
        index = self.storage.load_proposer_index()
        # Corrected path to look inside the 'proposers' sub-dictionary
        proposer_index = index.get('proposers', {})
        ids = proposer_index.get("duties_by_epoch", {}).get(str(epoch), [])
        return [self.get_proposal_by_id(pid) for pid in ids if self.get_proposal_by_id(pid)]

    def get_proposer_summary(self) -> Dict[str, Any]:
        index = self.storage.load_proposer_index()
        all_proposals = [self.storage.load_proposal(pid) for pid in self.storage.list_proposal_ids()]
        return proposer_helper.build_summary(index, all_proposals)

    def close(self) -> None:
        self.storage.close()
        if self.validator_index_service:
            self.validator_index_service.close()
        if self.mempool_index_service:
            self.mempool_index_service.close()
        if self.blockchain_index_service:
            self.blockchain_index_service.close()
