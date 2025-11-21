#!/usr/bin/env python3
"""finalizer_lib_api.py - Public API for the self-contained finalizer module."""

from typing import Dict, Any, Optional

from BachiCoin.lib_finalizer.finalizer_service_factory import FinalizerServiceFactory
from BachiCoin.lib_finalizer.finalizer_index_service import FinalizerIndexService
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg

# =================== FACTORY FUNCTION ===================

def create_finalizer_index_service(*args, **kwargs) -> FinalizerIndexService:
    """
    Creates a new instance of the FinalizerIndexService, allowing dependency injection.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(
        FinalizerServiceFactory.create_finalizer_index_service, *args, **kwargs
    )

def process_epoch_finality(service: FinalizerIndexService, epoch: int) -> Optional[Dict[str, Any]]:
    """Processes attestations for an epoch to determine checkpoint finality."""
    return service.process_epoch_finality(epoch)

def update_checkpoint_status(service: FinalizerIndexService, epoch: int, new_status: str) -> bool:
    """Updates the status of a checkpoint."""
    return service.update_checkpoint_status(epoch, new_status)

def get_checkpoint(service: FinalizerIndexService, epoch: int) -> Optional[Dict[str, Any]]:
    """Gets a checkpoint's full data by its epoch."""
    return service.get_checkpoint(epoch)

def get_latest_justified_checkpoint(service: FinalizerIndexService) -> Optional[Dict[str, Any]]:
    """Gets the most recently justified checkpoint."""
    return service.get_latest_justified_checkpoint()

def get_latest_finalized_checkpoint(service: FinalizerIndexService) -> Optional[Dict[str, Any]]:
    """Gets the most recently finalized checkpoint."""
    return service.get_latest_finalized_checkpoint()

def get_finality_summary(service: FinalizerIndexService) -> Dict[str, Any]:
    """Gets a high-level summary of the chain's finality."""
    return service.get_finality_summary()


if __name__ == "__main__":
    """Functional test for the Finalizer Public API (using existing data)."""
    from tests.test_config import dirs
    from BachiCoin.lib_finalizer.finalizer_config import FinalityStatus
    from BachiCoin.api_public import attestor_lib_api, blockchain_lib_api, validator_lib_api

    print("=== Finalizer Public API Functional Test (using existing data) ===")

    print("\n🧪 1. Creating finalizer service and loading existing data...")
    # Create dependent services first
    attestor_service = attestor_lib_api.create_attestor_index_service(dirs)
    blockchain_service = blockchain_lib_api.create_blockchain_index_service(dirs)
    validator_service = validator_lib_api.create_validator_index_service(dirs)

    # Inject dependencies into the finalizer service
    service = create_finalizer_index_service(
        dirs,
        attestor_service=attestor_service,
        blockchain_service=blockchain_service,
        validator_service=validator_service
    )
    print("✅ Service created.")

    print("\n🧪 2. Getting initial finality summary...")
    initial_summary = get_finality_summary(service)
    print(f"   - Initial Summary: {initial_summary}")
    assert "justified_epoch" in initial_summary
    assert "finalized_epoch" in initial_summary

    # We will attempt to process the epoch after the last known justified one.
    test_epoch = initial_summary.get("justified_epoch", -1) + 1
    print(f"\n🧪 3. Attempting to process finality for epoch {test_epoch}...")
    new_checkpoint = process_epoch_finality(service, test_epoch)

    if new_checkpoint:
        print(f"✅ Finality processed for epoch {test_epoch}.")
        assert new_checkpoint["epoch"] == test_epoch

        print("\n🧪 4. Verifying updated state...")
        retrieved_checkpoint = get_checkpoint(service, test_epoch)
        assert retrieved_checkpoint is not None
        assert retrieved_checkpoint["status"] == FinalityStatus.JUSTIFIED.value
        print(f"   - get_checkpoint({test_epoch}): OK")

        latest_justified = get_latest_justified_checkpoint(service)
        assert latest_justified["epoch"] == test_epoch
        print(f"   - get_latest_justified_checkpoint(): OK, epoch {latest_justified['epoch']}")
    else:
        print(f"ℹ️  Could not process finality for epoch {test_epoch}. This may be expected if no supermajority was reached.")

    service.close()
    print("\n✅ Finalizer Public API Test Complete!")
