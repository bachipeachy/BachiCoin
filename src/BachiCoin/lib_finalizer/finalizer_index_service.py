#!/usr/bin/env python3
"""finalizer_index_service.py – Thin orchestrator for Casper FFG finality duties."""

from typing import Dict, Any, Optional
from datetime import datetime
from BachiCoin.lib_finalizer import finalizer_helper
from BachiCoin.lib_finalizer.finalizer_config import (
    FinalizerConfig,
    FinalityStatus,
    is_valid_finality_status,
)
from BachiCoin.lib_finalizer.finalizer_validation import assert_valid_for_update
from BachiCoin.lib_finalizer.finalizer_storage_adapter import FinalizerStorageAdapter
from BachiCoin.lib_validator.validator_config import ValidatorStatus
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_attestor.attestor_index_service import AttestorIndexService
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService


class FinalizerIndexService:
    """Manages justified and finalized checkpoints."""

    def __init__(self,
                 storage_adapter: FinalizerStorageAdapter,
                 attestor_index_service: AttestorIndexService,
                 validator_index_service: ValidatorIndexService,
                 blockchain_index_service: BlockchainIndexService):
        """Initializes the service with all dependencies injected."""
        assert storage_adapter, "A valid storage_adapter is required"
        assert attestor_index_service, "A valid attestor_index_service is required"
        assert validator_index_service, "A valid validator_index_service is required"
        assert blockchain_index_service, "A valid blockchain_index_service is required"

        self.storage = storage_adapter
        self.attestor_index_service = attestor_index_service
        self.validator_index_service = validator_index_service
        self.blockchain_index_service = blockchain_index_service
        self.config = FinalizerConfig()

    def _update_finality_in_index(self, justified_epoch: int, finalized_epoch: int) -> None:
        def update_func(index_data: Dict[str, Any]) -> Dict[str, Any]:
            return finalizer_helper.update_finality_in_index(index_data, justified_epoch, finalized_epoch)
        assert self.storage.update_finalizer_index(update_func), "Failed to update finalizer index"

    def _add_checkpoint_to_index(self, epoch: int, root: str) -> None:
        def update_func(index_data: Dict[str, Any]) -> Dict[str, Any]:
            return finalizer_helper.add_checkpoint_to_index(index_data, epoch, root)
        assert self.storage.update_finalizer_index(update_func), "Failed to add checkpoint to index"

    def process_epoch_finality(self, epoch: int) -> Optional[Dict[str, Any]]:
        """
        Processes attestations for a given epoch to determine if it can be
        justified or finalized.
        """
        # Use direct service call
        all_attestations = self.attestor_index_service.get_attestations_for_epoch(epoch)
        successful_attestations = [
            att for att in all_attestations if att.get("status") == "included_success"
        ]

        if not successful_attestations:
            print(f"   [Finalizer] No successful attestations found for epoch {epoch}.")
            return None

        target_votes, total_stake = finalizer_helper.tally_attestations(
            successful_attestations, self.validator_index_service
        )

        if not target_votes:
            print(f"   [Finalizer] No valid votes found in attestations for epoch {epoch}.")
            return None

        (winning_root, winning_epoch), participating_stake = target_votes.most_common(1)[0]

        supermajority = participating_stake * 3 >= total_stake * 2

        if not supermajority:
            print(f"   [Finalizer] ⚠️ No supermajority for epoch {epoch} ({participating_stake}/{total_stake} stake)." )
            return None

        index = self.storage.load_finalizer_index()
        prev_justified_epoch = index['finalizers']["metadata"]["justified_epoch"]
        prev_finalized_epoch = index['finalizers']["metadata"]["finalized_epoch"]

        checkpoint_data = finalizer_helper.create_checkpoint_data(winning_epoch, winning_root)
        self.storage.save_checkpoint(winning_epoch, checkpoint_data)
        self._add_checkpoint_to_index(winning_epoch, winning_root)
        self._update_block_statuses_for_epoch(winning_epoch, FinalityStatus.JUSTIFIED.value)

        finalized_epoch_msg = ""
        if prev_justified_epoch >= 0 and prev_justified_epoch == winning_epoch - 1:
            self.update_checkpoint_status(prev_justified_epoch, FinalityStatus.FINALIZED.value)
            self._update_block_statuses_for_epoch(prev_justified_epoch, FinalityStatus.FINALIZED.value)
            self._update_finality_in_index(justified_epoch=winning_epoch, finalized_epoch=prev_justified_epoch)
            finalized_epoch_msg = f" Finalized epoch {prev_justified_epoch}."
        else:
            self._update_finality_in_index(justified_epoch=winning_epoch, finalized_epoch=prev_finalized_epoch)

        summary_msg = (
            f"✅ Supermajority on {winning_root[:10]}... ({participating_stake}/{total_stake} stake). "
            f"Justified epoch {winning_epoch}.{finalized_epoch_msg}"
        )
        print(f"   [Finalizer] {summary_msg}")

        return self.get_checkpoint(winning_epoch)

    def update_checkpoint_status(self, epoch: int, new_status: str) -> bool:
        assert is_valid_finality_status(new_status), f"Invalid status: {new_status}"
        payload = {"status": new_status}
        if new_status == FinalityStatus.FINALIZED.value:
            payload["finalized_at"] = datetime.now().isoformat() + "Z"
        assert_valid_for_update(payload)

        def update_func(checkpoint_data: Dict[str, Any]) -> Dict[str, Any]:
            checkpoint_data.update(payload)
            return checkpoint_data

        updated = self.storage.update_checkpoint(epoch, update_func)
        return updated is not None

    def get_checkpoint(self, epoch: int) -> Optional[Dict[str, Any]]:
        return self.storage.load_checkpoint(epoch)

    def get_latest_justified_checkpoint(self) -> Optional[Dict[str, Any]]:
        index = self.storage.load_finalizer_index()
        epoch = index['finalizers']["metadata"]["justified_epoch"]
        return self.get_checkpoint(epoch) if epoch != -1 else None

    def get_latest_finalized_checkpoint(self) -> Optional[Dict[str, Any]]:
        index = self.storage.load_finalizer_index()
        epoch = index['finalizers']["metadata"]["finalized_epoch"]
        return self.get_checkpoint(epoch) if epoch != -1 else None

    def get_finality_summary(self) -> Dict[str, Any]:
        index = self.storage.load_finalizer_index()
        return {
            "justified_epoch": index['finalizers']["metadata"]["justified_epoch"],
            "finalized_epoch": index['finalizers']["metadata"]["finalized_epoch"],
            "last_updated": index['finalizers']["metadata"]["last_updated"],
        }

    def _update_validator_statuses_for_epoch(self, epoch: int):
        # Use direct service call
        attestations = self.attestor_index_service.get_attestations_for_epoch(epoch)
        participating_validators = {att['validator_index'] for att in attestations}
        for validator_index in participating_validators:
            # Use direct service call
            self.validator_index_service.update_validator_status(validator_index, ValidatorStatus.ACTIVE_ONGOING.value)

    def _update_block_statuses_for_epoch(self, epoch: int, status: str):
        start_slot, end_slot = finalizer_helper.epoch_slot_range(epoch)
        # Use direct service call
        blocks_in_epoch = self.blockchain_index_service.get_blocks_by_slot_range(start_slot, end_slot)
        for block_info in blocks_in_epoch:
            # Use direct service call
            self.blockchain_index_service.update_block(block_info["block_hash"], {"status": status})

    def close(self) -> None:
        self.storage.close()
        if self.attestor_index_service:
            self.attestor_index_service.close()
        if self.validator_index_service:
            self.validator_index_service.close()
        if self.blockchain_index_service:
            self.blockchain_index_service.close()
