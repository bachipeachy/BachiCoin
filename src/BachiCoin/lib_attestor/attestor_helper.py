#!/usr/bin/env python3
"""
attestor_helper.py – Pure helper logic for attestation duties.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from collections import Counter
from BachiCoin.lib_attestor.attestor_config import AttestorStatus


def update_index_with_attestation(index_data: Dict[str, Any], attestation_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add an attestation duty to the nested attestors object in index_data."""
    attestation_id = attestation_data["attestation_id"]
    epoch = str(attestation_data["epoch"])
    validator_index = str(attestation_data["validator_index"])

    # Ensure the primary 'attestors' key exists and get the nested object.
    attestors_data = index_data.setdefault("attestors", {})

    # Update duties, correctly nested under 'attestors'.
    duties_by_epoch = attestors_data.setdefault("duties_by_epoch", {})
    duties_by_epoch.setdefault(epoch, []).append(attestation_id)

    duties_by_validator = attestors_data.setdefault("duties_by_validator", {})
    duties_by_validator.setdefault(validator_index, []).append(attestation_id)

    # Update metadata, correctly nested under 'attestors'.
    metadata = attestors_data.setdefault("metadata", {})
    metadata["total_duties_assigned"] = metadata.get("total_duties_assigned", 0) + 1
    metadata["last_assigned_epoch"] = max(metadata.get("last_assigned_epoch", -1), int(epoch))
    metadata["last_updated"] = datetime.now().isoformat() + "Z"
    
    return index_data


def create_attestation_data(slot: int, epoch: int, validator_index: int, committee_index: int) -> Dict[str, Any]:
    """Creates a new attestation duty record with default values."""
    attestation_id = f"{slot}-{validator_index}"
    return {
        "attestation_id": attestation_id,
        "slot": slot,
        "epoch": epoch,
        "validator_index": validator_index,
        "committee_index": committee_index,
        "status": AttestorStatus.AWAITING_DUTY.value,
        "created_at": datetime.now().isoformat() + "Z",
    }


def build_summary(index_data: Dict[str, Any], all_attestations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a high-level summary from index_data and attestations."""
    summary = {
        "total_duties": index_data['attestors']["metadata"]["total_duties_assigned"],
        "last_assigned_epoch": index_data['attestors']["metadata"]["last_assigned_epoch"],
        "by_status": {},
    }
    for attestation in all_attestations:
        if attestation:
            status = attestation.get("status", "unknown")
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
    return summary

def tally_attestations(attestations: List[Dict[str, Any]], validator_service) -> Tuple[Counter, int]:
    """Tally votes (attestations) for checkpoint targets"""
    target_votes = Counter()
    validator_stake = {}
    for att in attestations:
        # 2. ADD THIS CHECK
        if att.get("status") != AttestorStatus.INCLUDED_SUCCESS.value:
            continue  # Only count votes from successful attestations

        target_root = att.get("target_root")
        target_epoch = att.get("target_epoch")
        validator_index = att.get("validator_index")
        if target_root and target_epoch is not None and validator_index is not None:
            if validator_index not in validator_stake:
                val_data = validator_service.get_validator(validator_index)
                validator_stake[validator_index] = val_data.get("effective_balance", 0)
            stake = validator_stake[validator_index]
            target_votes[(target_root, target_epoch)] += stake

    total_stake = validator_service.get_validator_summary().get("total_effective_balance", 0)
    return target_votes, total_stake
