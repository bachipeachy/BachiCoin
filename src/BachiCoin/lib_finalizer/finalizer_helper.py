#!/usr/bin/env python3
"""
finalizer_helper.py – Pure helper logic for Casper FFG finality duties.
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from collections import Counter

# Local Imports
from BachiCoin.lib_finalizer.finalizer_config import FinalityStatus
from BachiCoin.lib_consensus.consensus_config import SLOTS_PER_EPOCH
from BachiCoin.lib_attestor.attestor_config import AttestorStatus

def update_finality_in_index(index_data: Dict[str, Any], justified_epoch: int, finalized_epoch: int) -> Dict[str, Any]:
    """Update the justified and finalized epochs in the nested metadata of index_data."""
    # Ensure the path exists, though the factory should create it.
    metadata = index_data.setdefault("finalizers", {}).setdefault("metadata", {})
    
    metadata["justified_epoch"] = justified_epoch
    metadata["finalized_epoch"] = finalized_epoch
    metadata["last_updated"] = datetime.now().isoformat() + "Z"
    
    return index_data

def add_checkpoint_to_index(index_data: Dict[str, Any], epoch: int, root: str) -> Dict[str, Any]:
    """Add a new checkpoint record to the nested checkpoints dictionary."""
    # Ensure the path exists
    checkpoints = index_data.setdefault("finalizers", {}).setdefault("checkpoints", {})
    
    # Create the new checkpoint data
    new_checkpoint = create_checkpoint_data(epoch, root)
    
    # Add it to the dictionary with the epoch as the key
    checkpoints[str(epoch)] = new_checkpoint
    
    return index_data

def create_checkpoint_data(epoch: int, root: str) -> Dict[str, Any]:
    """Creates a new checkpoint record with default values."""
    return {
        "epoch": epoch,
        "root": root,
        "status": FinalityStatus.JUSTIFIED.value,
        "justified_at": datetime.now().isoformat() + "Z",
    }

def tally_attestations(
        all_attestations_for_epoch: List[Dict[str, Any]],
        validator_service
) -> Tuple[Counter, int]:
    """Tally votes from successful attestations for checkpoint targets."""
    target_votes = Counter()
    validator_stake_cache = {}

    successful_attestations = [
        att for att in all_attestations_for_epoch
        if att.get("status") == AttestorStatus.INCLUDED_SUCCESS.value
    ]

    for att in successful_attestations:
        target_root = att.get("target_root")
        target_epoch = att.get("epoch")
        validator_index = att.get("validator_index")

        if not (target_root and target_epoch is not None and validator_index is not None):
            continue

        if validator_index not in validator_stake_cache:
            val_data = validator_service.get_validator(validator_index)
            stake = val_data.get("effective_balance", 0) if val_data else 0
            validator_stake_cache[validator_index] = stake
        else:
            stake = validator_stake_cache[validator_index]

        if stake > 0:
            target_votes[(target_root, target_epoch)] += stake

    total_stake = validator_service.get_validator_summary().get("total_effective_balance", 0)
    return target_votes, total_stake

def epoch_slot_range(epoch: int) -> Tuple[int, int]:
    """Compute start and end slot for an epoch."""
    start_slot = epoch * SLOTS_PER_EPOCH
    end_slot = start_slot + SLOTS_PER_EPOCH - 1
    return start_slot, end_slot
