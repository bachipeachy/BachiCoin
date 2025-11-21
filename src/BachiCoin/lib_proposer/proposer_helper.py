#!/usr/bin/env python3
"""
proposer_helper.py – Pure helper logic for proposer duties.
This module contains all pure functions used by ProposerIndexService.
"""

from typing import Dict, Any, List
from datetime import datetime
from BachiCoin.lib_proposer.proposer_config import ProposerStatus
from BachiCoin.lib_consensus.consensus_config import SLOTS_PER_EPOCH


def create_proposal_data(slot: int, validator_index: int) -> Dict[str, Any]:
    """Creates a new proposal duty record with default values."""
    epoch = slot // SLOTS_PER_EPOCH
    proposal_id = f"{epoch}-{slot}"
    return {
        "proposal_id": proposal_id,
        "slot": slot,
        "epoch": epoch,
        "validator_index": validator_index,
        "status": ProposerStatus.AWAITING_DUTY.value,
        "block_hash": None,
        "payload_size_bytes": 0,
        "transaction_count": 0,
        "proposed_at": None,
        "error_message": None,
    }


def update_index_with_proposal(index_data: Dict[str, Any], proposal_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a proposal duty to the nested proposers object in index_data."""
    proposal_id = proposal_data["proposal_id"]
    slot = str(proposal_data["slot"])
    epoch = str(proposal_data["epoch"])

    # Ensure the primary 'proposers' key exists and get the nested object.
    proposers_data = index_data.setdefault("proposers", {})

    # Update duties, correctly nested under 'proposers'.
    proposers_data.setdefault("duties_by_slot", {})[slot] = proposal_id
    proposers_data.setdefault("duties_by_epoch", {}).setdefault(epoch, []).append(proposal_id)

    # Update metadata, correctly nested under 'proposers'.
    metadata = proposers_data.setdefault("metadata", {})
    metadata["total_duties_assigned"] = metadata.get("total_duties_assigned", 0) + 1
    metadata["last_assigned_slot"] = max(metadata.get("last_assigned_slot", -1), int(slot))
    metadata["last_updated"] = datetime.now().isoformat() + "Z"
    
    return index_data


def build_summary(index_data: Dict[str, Any], all_proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a high-level summary from index_data and proposals."""
    summary = {
        "total_duties": index_data['proposers']["metadata"]["total_duties_assigned"],
        "last_assigned_slot": index_data['proposers']["metadata"]["last_assigned_slot"],
        "by_status": {},
    }
    for proposal in all_proposals:
        if proposal:
            status = proposal.get("status", "unknown")
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
    return summary
