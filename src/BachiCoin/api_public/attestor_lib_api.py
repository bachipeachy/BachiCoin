#!/usr/bin/env python3
"""attestor_lib_api.py - Public API for the self-contained attestor module."""

from typing import Dict, Any, Optional, List

from BachiCoin.lib_attestor.attestor_service_factory import AttestorServiceFactory
from BachiCoin.lib_attestor.attestor_index_service import AttestorIndexService
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg

# =================== FACTORY FUNCTION ===================

def create_attestor_index_service(*args, **kwargs) -> AttestorIndexService:
    """
    Creates a new instance of the AttestorIndexService, allowing dependency injection.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(
        AttestorServiceFactory.create_attestor_index_service, *args, **kwargs
    )

# =================== PUBLIC API WRAPPERS ===================

def assign_attestation_duties_for_epoch(service: AttestorIndexService, epoch: int) -> List[str]:
    """Forms committees and assigns attestation duties for an entire epoch."""
    return service.assign_attestation_duties_for_epoch(epoch)

def simulate_and_record_attestations_for_slot(service: AttestorIndexService, slot: int, block_hash: str):
    """Simulates validators creating and submitting attestations for the current slot."""
    return service.simulate_and_record_attestations_for_slot(slot, block_hash)

def update_attestation_status(
        service: AttestorIndexService,
        attestation_id: str,
        new_status: str,
        update_payload: Optional[Dict[str, Any]] = None
) -> bool:
    """Updates the status and optional data of an attestation duty."""
    return service.update_attestation_status(attestation_id, new_status, update_payload)

def get_attestation_by_id(service: AttestorIndexService, attestation_id: str) -> Optional[Dict[str, Any]]:
    """Gets an attestation's full data by its unique ID."""
    return service.get_attestation_by_id(attestation_id)


def get_attestations_for_epoch(service: AttestorIndexService, epoch: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Gets all attestation duties assigned within a specific epoch, with optional status filter."""
    return service.get_attestations_for_epoch(epoch, status=status)


def get_attestations_for_validator(
        service: AttestorIndexService,
        validator_index: int,
        epoch_filter: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Gets all attestation duties for a specific validator."""
    return service.get_attestations_for_validator(validator_index, epoch_filter)


def get_attestor_summary(service: AttestorIndexService) -> Dict[str, Any]:
    """Gets a high-level summary of all attestation duties."""
    return service.get_attestor_summary()


if __name__ == "__main__":
    """Functional test for the Attestor Public API (using existing data)."""
    from BachiCoin.lib_attestor.attestor_config import AttestorStatus
    from BachiCoin.api_public.user_lib_api import create_user_index_service
    from BachiCoin.api_public.wallet_lib_api import create_wallet_index_service
    from BachiCoin.api_public.validator_lib_api import create_validator_index_service, get_active_validators
    from tests.test_config import dirs

    print("=== Attestor Public API Functional Test (using existing data) ===")

    print("\n🧪 1. Creating services and loading existing data...")
    user_index_service = create_user_index_service(dirs)
    wallet_index_service = create_wallet_index_service(dirs)
    validator_index_service = create_validator_index_service(dirs, user_service=user_index_service, wallet_service=wallet_index_service)
    service = create_attestor_index_service(dirs, validator_service=validator_index_service)
    print("✅ Services created.")

    print("\n🧪 2. Finding existing active validators...")
    active_validators = get_active_validators(validator_index_service)
    assert active_validators, "Test requires at least one active validator, but none were found."
    validator_to_test_index = active_validators[0]
    print(f"✅ Found {len(active_validators)} active validators. Using index {validator_to_test_index} for tests.")

    print("\n🧪 3. Testing duty assignment for a new epoch...")
    summary = get_attestor_summary(service)
    test_epoch = summary.get("last_assigned_epoch", -1) + 1
    print(f"   - Assigning duties for epoch {test_epoch}...")
    assigned_ids = assign_attestation_duties_for_epoch(service, test_epoch)
    print(f"✅ {len(assigned_ids)} duties assigned for epoch {test_epoch}.")
    # Assuming 32 slots per epoch for the test assertion
    assert len(assigned_ids) == len(active_validators) * 32

    print("\n🧪 4. Testing attestation retrieval...")
    attestations_for_epoch = get_attestations_for_epoch(service, test_epoch)
    assert len(attestations_for_epoch) == len(assigned_ids)
    print(f"   - Retrieved by epoch: {len(attestations_for_epoch)} OK")

    attestations_for_validator = get_attestations_for_validator(
        service, validator_to_test_index, epoch_filter=test_epoch
    )
    assert len(attestations_for_validator) == 32  # One duty per slot in the epoch
    print(f"   - Retrieved by validator for epoch: {len(attestations_for_validator)} OK")

    print("\n🧪 5. Testing status update...")
    attestation_to_update = attestations_for_epoch[0]
    attestation_id = attestation_to_update["attestation_id"]
    updated = update_attestation_status(
        service, attestation_id, AttestorStatus.INCLUDED_SUCCESS.value
    )
    assert updated, "Update failed"
    updated_attestation = get_attestation_by_id(service, attestation_id)
    print(f"   - New status: {updated_attestation['status']}")
    assert updated_attestation["status"] == AttestorStatus.INCLUDED_SUCCESS.value

    print("\n🧪 6. Testing summary...")
    new_summary = get_attestor_summary(service)
    print(f"   - Summary: {new_summary}")
    assert new_summary["total_duties"] > 0
    assert new_summary["by_status"].get(AttestorStatus.INCLUDED_SUCCESS.value, 0) >= 1

    service.close()
    print("\n✅ Attestor Public API Test Complete!")
