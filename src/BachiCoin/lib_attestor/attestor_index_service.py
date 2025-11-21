#!/usr/bin/env python3
"""attestor_index_service.py – Thin orchestrator for attestation duties."""

from typing import Dict, Any, Optional, List
from BachiCoin.lib_attestor import attestor_helper
from BachiCoin.lib_attestor.attestor_config import (
    AttestorConfig,
    AttestorStatus,
    is_valid_attestation_status,
)
from BachiCoin.lib_attestor.attestor_validation import (
    assert_valid_for_creation,
    assert_valid_for_update,
)
from BachiCoin.lib_attestor.attestor_storage_adapter import AttestorStorageAdapter
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_consensus.consensus_config import SLOTS_PER_EPOCH


class AttestorIndexService:
    """Thin service delegating attestation logic to attestor_helper."""

    def __init__(self, storage_adapter: AttestorStorageAdapter, validator_index_service: ValidatorIndexService):
        """Initializes the service with all dependencies injected."""
        assert storage_adapter, "A valid storage_adapter is required"
        assert validator_index_service, "A valid validator_index_service is required"

        self.storage = storage_adapter
        self.validator_index_service = validator_index_service
        self.config = AttestorConfig()

    def _add_duty_to_indices(self, attestation_data: Dict[str, Any]) -> None:
        def update_func(index_data: Dict[str, Any]) -> Dict[str, Any]:
            return attestor_helper.update_index_with_attestation(index_data, attestation_data)
        assert self.storage.update_attestor_index(update_func), "Failed to update attestor index"

    def assign_attestation_duties_for_epoch(self, epoch: int) -> List[str]:
        # Use direct service call
        active_validators = self.validator_index_service.get_active_validators()
        assert active_validators, f"No active validators to assign duties for epoch {epoch}."

        index = self.storage.load_attestor_index()
        attestors_data = index.get("attestors", {})
        assert str(epoch) not in attestors_data.get("duties_by_epoch", {}), f"Duties for epoch {epoch} have already been assigned."

        assigned_ids = []
        slots_per_epoch = SLOTS_PER_EPOCH
        start_slot = epoch * slots_per_epoch

        for slot_offset in range(slots_per_epoch):
            current_slot = start_slot + slot_offset
            committee_index = 0  # simplified
            for validator_index in active_validators:
                attestation_data = attestor_helper.create_attestation_data(current_slot, epoch, validator_index, committee_index)
                assert_valid_for_creation(attestation_data)

                attestation_id = attestation_data["attestation_id"]
                assert self.storage.save_attestation(attestation_id, attestation_data), f"Failed to save attestation {attestation_id}"
                self._add_duty_to_indices(attestation_data)
                assigned_ids.append(attestation_id)
        return assigned_ids

    def simulate_and_record_attestations_for_slot(self, slot: int, block_hash: str):
        epoch = slot // SLOTS_PER_EPOCH
        attestations_for_epoch = self.get_attestations_for_epoch(epoch)
        duties_for_this_slot = [a for a in attestations_for_epoch if a.get("slot") == slot]
        for duty in duties_for_this_slot:
            payload = {
                "target_root": block_hash,
                "target_epoch": epoch,
            }
            self.update_attestation_status(duty["attestation_id"], AttestorStatus.INCLUDED_SUCCESS.value, payload)

    def update_attestation_status(self, attestation_id: str, new_status: str,
                                 update_payload: Optional[Dict[str, Any]] = None) -> bool:
        assert is_valid_attestation_status(new_status), f"Invalid status: {new_status}"
        payload = update_payload or {}
        payload["status"] = new_status
        assert_valid_for_update(payload)

        def update_func(attestation_data: Dict[str, Any]) -> Dict[str, Any]:
            attestation_data.update(payload)
            return attestation_data

        updated = self.storage.update_attestation(attestation_id, update_func)
        return updated is not None

    def get_attestation_by_id(self, attestation_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_attestation(attestation_id)

    def get_attestations_for_epoch(self, epoch: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Gets all attestation duties assigned within a specific epoch, with optional status filter."""
        index = self.storage.load_attestor_index()
        attestors_data = index.get("attestors", {})
        attestation_ids = attestors_data.get("duties_by_epoch", {}).get(str(epoch), [])
        
        attestations = [
            self.get_attestation_by_id(aid)
            for aid in attestation_ids
            if self.get_attestation_by_id(aid) is not None
        ]
        
        if status:
            return [att for att in attestations if att.get("status") == status]
        return attestations

    def get_attestations_for_validator(self, validator_index: int, epoch_filter: Optional[int] = None) -> List[Dict[str, Any]]:
        index = self.storage.load_attestor_index()
        attestors_data = index.get("attestors", {})
        attestation_ids = attestors_data.get("duties_by_validator", {}).get(str(validator_index), [])
        attestations = [self.get_attestation_by_id(aid) for aid in attestation_ids if self.get_attestation_by_id(aid)]
        if epoch_filter is not None:
            return [a for a in attestations if a.get("epoch") == epoch_filter]
        return attestations

    def get_attestor_summary(self) -> Dict[str, Any]:
        index = self.storage.load_attestor_index()
        all_attestations = [self.storage.load_attestation(aid) for aid in self.storage.list_attestation_ids()]
        return attestor_helper.build_summary(index, all_attestations)

    def close(self) -> None:
        self.storage.close()
        if self.validator_index_service:
            self.validator_index_service.close()
