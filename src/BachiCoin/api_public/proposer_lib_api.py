#!/usr/bin/env python3
"""proposer_lib_api.py - Public API for the Proposer module"""

from typing import Dict, Any, Optional, List

from BachiCoin.lib_proposer.proposer_index_service import ProposerIndexService
from BachiCoin.lib_proposer.proposer_service_factory import ProposerServiceFactory
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg

# --- Factory Function --- #
def create_proposer_index_service(*args, **kwargs) -> ProposerIndexService:
    """
    Factory to create a ProposerIndexService, allowing dependency injection.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(
        ProposerServiceFactory.create_proposer_index_service, *args, **kwargs
    )

# --- Public API Wrappers --- #

def assign_proposal_duty(service: ProposerIndexService, slot: int, validator_index: int) -> Optional[str]:
    """Assigns a proposal duty to a validator for a specific slot."""
    return service.assign_proposal_duty(slot, validator_index)

def build_candidate_block(service: ProposerIndexService, slot: int) -> Optional[Dict[str, Any]]:
    """Builds a candidate block for a given slot. Does NOT save the block."""
    return service.build_candidate_block(slot)

def update_proposal_status_after_commit(service: ProposerIndexService, block_data: Dict[str, Any]) -> bool:
    """Updates the proposal duty status after a block has been successfully committed."""
    return service.update_proposal_status_after_commit(block_data)

def get_proposal_by_id(service: ProposerIndexService, proposal_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a specific proposal duty by its ID."""
    return service.get_proposal_by_id(proposal_id)

def get_proposal_by_slot(service: ProposerIndexService, slot: int) -> Optional[Dict[str, Any]]:
    """Retrieve a proposal duty by its assigned slot."""
    return service.get_proposal_by_slot(slot)

def get_proposals_for_epoch(service: ProposerIndexService, epoch: int) -> List[Dict[str, Any]]:
    """Retrieves all proposal duties for a given epoch."""
    return service.get_proposals_for_epoch(epoch)

def get_proposer_summary(service: ProposerIndexService) -> Dict[str, Any]:
    """Retrieves a summary of all proposer duties and metadata."""
    return service.get_proposer_summary()


if __name__ == "__main__":
    """Functional test for the Proposer Public API (using existing data)."""
    from tests.test_config import dirs
    from BachiCoin.api_public import validator_lib_api
    from BachiCoin.lib_proposer.proposer_config import ProposerStatus

    print("=== Proposer Public API Functional Test (using existing data) ===")

    print("\n🧪 1. Creating services and loading existing data...")
    validator_service = validator_lib_api.create_validator_index_service(dirs)
    service = create_proposer_index_service(dirs, validator_service=validator_service)
    print("✅ Proposer and Validator services created.")

    print("\n🧪 2. Finding an active validator to act as proposer...")
    active_validators = validator_lib_api.get_active_validators(validator_service)
    assert active_validators, "Test requires at least one active validator, but none were found."
    proposer_index = active_validators[0]
    print(f"✅ Found {len(active_validators)} active validators. Using index {proposer_index} for tests.")

    # Define a test slot and epoch. We assume 32 slots per epoch.
    test_slot = 128
    test_epoch = test_slot // 32

    print(f"\n🧪 3. Assigning a proposal duty for slot {test_slot}...")
    proposal_id = assign_proposal_duty(service, test_slot, proposer_index)
    assert proposal_id, "Failed to assign proposal duty; received a null or empty ID."
    print(f"✅ Proposal duty assigned successfully. ID: {proposal_id}")

    print("\n🧪 4. Testing proposal retrieval functions...")
    # Test get by ID
    proposal_by_id = get_proposal_by_id(service, proposal_id)
    assert proposal_by_id is not None, "get_proposal_by_id failed to retrieve the duty."
    assert proposal_by_id["slot"] == test_slot
    assert proposal_by_id["validator_index"] == proposer_index
    print("   - get_proposal_by_id(): OK")

    # Test get by slot
    proposal_by_slot = get_proposal_by_slot(service, test_slot)
    assert proposal_by_slot is not None, "get_proposal_by_slot failed to retrieve the duty."
    assert proposal_by_slot["proposal_id"] == proposal_id
    print("   - get_proposal_by_slot(): OK")

    # Test get by epoch
    proposals_for_epoch = get_proposals_for_epoch(service, test_epoch)
    assert any(p["proposal_id"] == proposal_id for p in proposals_for_epoch)
    print(f"   - get_proposals_for_epoch(): OK, found {len(proposals_for_epoch)} duties for epoch {test_epoch}.")

    print("\n🧪 5. Testing block building and status update...")
    # This simulates the proposer building a block. It does not save it.
    candidate_block = build_candidate_block(service, test_slot)
    assert candidate_block is not None, "build_candidate_block failed."
    assert candidate_block["header"]["slot"] == test_slot
    print("   - build_candidate_block(): OK, candidate block created.")

    # This simulates the block being accepted and updates the duty status.
    updated = update_proposal_status_after_commit(service, candidate_block)
    assert updated, "update_proposal_status_after_commit failed."
    updated_proposal = get_proposal_by_id(service, proposal_id)
    assert updated_proposal["status"] == ProposerStatus.PROPOSAL_SUCCESS.value
    print(f"   - update_proposal_status_after_commit(): OK, status is now '{updated_proposal['status']}'.")

    service.close()
    validator_service.close()
    print("\n✅ Proposer Public API Test Complete!")
