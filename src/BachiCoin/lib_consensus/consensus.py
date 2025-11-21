#!/usr/bin/env python3
"""consensus_service.py - functional orchestrator for proposer, attestor, and finalizer logic."""

from typing import Dict, Any, Optional, Generator

from BachiCoin.lib_crossmodule.node_context import NodeContext

from BachiCoin.lib_blockchain.blockchain_builder import prepare_genesis_block_data

from BachiCoin.lib_consensus.consensus_config import SLOTS_PER_EPOCH
from BachiCoin.lib_attestor.attestor_config import AttestorStatus
from BachiCoin.lib_proposer.proposer_config import ProposerStatus


def initialize_chain_if_needed(node_context: NodeContext) -> Dict[str, Any]:
    """Create genesis block if chain is empty and return tip."""
    blockchain_service = node_context.blockchain_service
    if blockchain_service.get_chain_height() == -1:
        print("   -> No chain tip found. Creating genesis block...")
        genesis_data = prepare_genesis_block_data("testnet") # Corrected call
        genesis_hash = blockchain_service.create_block_with_index(genesis_data)
        blockchain_service.set_chain_tip(genesis_hash, 0)
        print(f"      ✅ Genesis block created: {genesis_hash[:16]}...")

    tip = blockchain_service.get_chain_tip()
    assert tip, "Failed to get chain tip after initialization."
    return tip


def propose_block_for_slot(
    node_context: NodeContext,
    slot: int,
    epoch: int,
    active_validators: list,
) -> Optional[str]:
    """Propose a block for the given slot, with attestations included."""
    proposer_service = node_context.proposer_service
    attestor_service = node_context.attestor_service
    blockchain_service = node_context.blockchain_service

    if not active_validators:
        print("   [Consensus] ⚠️ No active validators to propose a block.")
        return None

    proposer_validator_index = active_validators[slot % len(active_validators)]
    proposal_id = proposer_service.assign_proposal_duty(slot, proposer_validator_index)

    candidate_block = proposer_service.build_candidate_block(slot)
    
    waiting_attestations = attestor_service.get_attestations_for_epoch(
        epoch, status=AttestorStatus.AWAITING_DUTY.value
    )
    
    # A block is only worth creating if it has transactions or attestations.
    # Access transactions from the body
    if not (candidate_block and candidate_block.get("body", {}).get("transactions")) and not waiting_attestations:
        # Update the proposal status to skipped if no block is created
        proposer_service.update_proposal_status(proposal_id, ProposerStatus.PROPOSAL_MISSED.value)
        return None

    candidate_block["body"]["attestations"] = waiting_attestations[:len(active_validators)]

    new_block_hash = blockchain_service.create_block_with_index(candidate_block)
    # Access height from the header
    blockchain_service.set_chain_tip(new_block_hash, candidate_block["header"]["height"])

    finalized_block_data = blockchain_service.get_block(new_block_hash)
    proposer_service.update_proposal_status_after_commit(finalized_block_data)

    final_proposal = proposer_service.get_proposal_by_slot(slot)
    assert final_proposal['status'] == ProposerStatus.PROPOSAL_SUCCESS.value
    return new_block_hash


def process_block_attestations(
    node_context: NodeContext,
    block_hash: str,
) -> int:
    """Update attestation statuses for a newly processed block."""
    attestor_service = node_context.attestor_service
    blockchain_service = node_context.blockchain_service
    block_data = blockchain_service.get_block(block_hash)
    if not block_data:
        return 0
        
    attestations = block_data.get("body", {}).get("attestations", [])
    if not attestations:
        return 0

    updated_count = 0
    for attestation in attestations:
        att_id = attestation.get("attestation_id")
        if not att_id:
            continue
        update_payload = {"target_root": block_hash, "target_epoch": block_data.get("header", {}).get("epoch")}
        attestor_service.update_attestation_status(
            att_id,
            AttestorStatus.INCLUDED_SUCCESS.value,
            update_payload,
        )
        updated_count += 1
    return updated_count


def finalize_epoch_if_needed(
    node_context: NodeContext,
    slot: int
) -> tuple[bool, Optional[int]]:
    """Run finalizer at end of epoch and update block statuses."""
    finalizer_service = node_context.finalizer_service
    blockchain_service = node_context.blockchain_service
    if (slot + 1) % SLOTS_PER_EPOCH != 0:
        return False, None

    finalizing_epoch = slot // SLOTS_PER_EPOCH
    print(f"   [Consensus] Running finalizer for epoch {finalizing_epoch}...")
    finality_result = finalizer_service.process_epoch_finality(finalizing_epoch)
    assert finality_result, f"Finalizer failed to process epoch {finalizing_epoch}."

    summary = finalizer_service.get_finality_summary()
    print(f"      ✅ Finality summary: Justified={summary.get('justified_epoch')}, Finalized={summary.get('finalized_epoch')}")

    # --- Persist finality status to the blocks themselves ---
    justified_epoch = summary.get('justified_epoch')
    finalized_epoch = summary.get('finalized_epoch')

    if justified_epoch is not None and justified_epoch >= 0:
        start_slot = justified_epoch * SLOTS_PER_EPOCH
        end_slot = start_slot + SLOTS_PER_EPOCH - 1
        blocks_to_justify = blockchain_service.get_blocks_by_slot_range(start_slot, end_slot)
        for block in blocks_to_justify:
            blockchain_service.update_block(block['block_hash'], {'justified': True})

    if finalized_epoch is not None and finalized_epoch >= 0:
        start_slot = finalized_epoch * SLOTS_PER_EPOCH
        end_slot = start_slot + SLOTS_PER_EPOCH - 1
        blocks_to_finalize = blockchain_service.get_blocks_by_slot_range(start_slot, end_slot)
        for block in blocks_to_finalize:
            blockchain_service.update_block(block['block_hash'], {'finalized': True})

    return True, summary.get("finalized_epoch")


def run_consensus(
    node_context: NodeContext,
    slots_to_run: int,
) -> Generator[Dict[str, Any], None, None]:
    """Run consensus loop for given number of slots."""
    blockchain_service = node_context.blockchain_service
    validator_service = node_context.validator_service
    attestor_service = node_context.attestor_service
    
    tip = initialize_chain_if_needed(node_context)
    active_validators = validator_service.get_active_validators()
    assert len(active_validators) > 0, "Consensus requires at least one active validator."

    for _ in range(slots_to_run):
        current_slot = tip.get("header", tip).get("slot", 0)
        next_slot = current_slot + 1
        epoch = next_slot // SLOTS_PER_EPOCH

        if not attestor_service.get_attestations_for_epoch(epoch):
            attestor_service.assign_attestation_duties_for_epoch(epoch)

        block_hash = propose_block_for_slot(node_context, next_slot, epoch, active_validators)
        if not block_hash:
            yield {"slot_processed": next_slot, "status": "skipped"}
            tip = blockchain_service.get_chain_tip() # Re-fetch tip in case of skipped slot
            continue
        
        process_block_attestations(node_context, block_hash)
        finalizer_run, finalized_epoch = finalize_epoch_if_needed(node_context, next_slot)

        tip = blockchain_service.get_block(block_hash)
        assert tip, f"Could not find newly created block {block_hash}"

        yield {
            "slot_processed": next_slot,
            "block_hash": block_hash,
            "proposer_index": tip.get("header", {}).get("proposer_index"),
            "transactions_included": len(tip.get("body", {}).get("transactions", [])),
            "attestations_submitted": len(tip.get("body", {}).get("attestations", [])),
            "finalizer_run": finalizer_run,
            "finalized_epoch": finalized_epoch,
        }
