#!/usr/bin/env python3
"""validator_lib_api.py - Public API for the self-contained validator module"""

from typing import Dict, Any, List, Optional

from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg
from BachiCoin.lib_validator.validator_config import ValidatorStatus as _ValidatorStatus

ValidatorStatus = _ValidatorStatus


# =================== FACTORY FUNCTION ===================

def create_validator_index_service(*args, **kwargs) -> ValidatorIndexService:
    """
    Creates a new instance of the ValidatorIndexService, allowing dependency injection.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(
        ValidatorServiceFactory.create_validator_index_service, *args, **kwargs
    )

# =================== PUBLIC API WRAPPERS ===================

def register_validator(
        service: ValidatorIndexService,
        user_id: str,
        wallet_id: str,
        withdrawal_credentials: str = None,
) -> Optional[int]:
    """Registers a user as a new validator."""
    return service.register_validator(user_id, wallet_id, withdrawal_credentials)

def get_validator(
        service: ValidatorIndexService, validator_index: int
) -> Optional[Dict[str, Any]]:
    """Retrieves the full data for a single validator by index."""
    return service.get_validator(validator_index)

def get_validator_by_user(
        service: ValidatorIndexService, user_id: str
) -> Optional[Dict[str, Any]]:
    """Retrieves validator data by the associated user ID."""
    return service.find_validator_by_user(user_id)

def get_validator_by_pubkey(
        service: ValidatorIndexService, pubkey: str
) -> Optional[Dict[str, Any]]:
    """Retrieves validator data by its public key."""
    return service.find_validator_by_pubkey(pubkey)

def get_active_validators(service: ValidatorIndexService) -> List[int]:
    """Retrieves a list of indices for all active validators."""
    return service.get_active_validators()

def get_pending_txs(
        service: ValidatorIndexService, mempool_index_service: MempoolIndexService, limit: int = None
) -> List[Dict[str, Any]]:
    """Fetches pending transactions from the mempool via the validator service."""
    return service.get_pending_txs(mempool_index_service, limit)

def filter_valid_txs(
        service: ValidatorIndexService,
        tx_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Filters and sorts a list of transactions for block inclusion."""
    return service.filter_valid_txs(tx_list)

def get_validator_summary(service: ValidatorIndexService) -> Dict[str, Any]:
    """Retrieves a high-level summary of the entire validator set."""
    return service.get_validator_summary()

def get_validator_counts(service: ValidatorIndexService) -> Dict[str, int]:
    """Retrieves a simple count of total and active validators."""
    return service.get_validator_counts()

def update_validator_status(
        service: ValidatorIndexService, validator_index: int, new_status: str
) -> bool:
    """Updates the status of a specific validator."""
    return service.update_validator_status(validator_index, new_status)

if __name__ == "__main__":
    """Unit test for the validator public API."""
    import asyncio
    from BachiCoin.lib_validator.validator_config import ValidatorStatus
    from BachiCoin.api_public.user_lib_api import create_user_index_service, list_users
    from BachiCoin.api_public.wallet_lib_api import create_wallet_index_service, list_wallets_by_user
    from tests.test_config import dirs

    async def run_tests():
        print("=== Validator Public API Functional Test (using existing data) ===")

        # 1. Create all services via their public API factories
        print("\n🧪 1. Creating services and loading existing data...")
        user_index_service = create_user_index_service(dirs)
        wallet_index_service = create_wallet_index_service(dirs)
        validator_index_service = create_validator_index_service(dirs, user_service=user_index_service, wallet_service=wallet_index_service)
        print("✅ All services created.")

        # 1.5 Bootstrap validators from existing users to ensure test data exists
        print("\n🧪 1.5. Bootstrapping validators from existing users...")
        all_users = list_users(user_index_service)
        regular_users = [u for u in all_users if u.get("user_type") != "system"]
        registered_count = 0
        for user in regular_users:
            user_id = user["user_id"]
            if get_validator_by_user(validator_index_service, user_id):
                print(f"   - User {user_id[:10]}... is already a validator. Skipping.")
                registered_count += 1
                continue

            user_wallets = list_wallets_by_user(wallet_index_service, user_id)
            if not user_wallets:
                print(f"   - ⚠️  User {user_id[:10]}... has no wallets. Cannot register.")
                continue

            wallet_id_to_use = user_wallets[0]["wallet_id"]
            print(f"   - Registering user {user_id[:10]}... with wallet {wallet_id_to_use[:10]}...")

            validator_index = register_validator(validator_index_service, user_id, wallet_id_to_use)
            if validator_index is not None:
                print(f"   - ✅ Successfully registered validator with index {validator_index}.")
                registered_count += 1
            else:
                print(f"   - ❌ Failed to register validator for user {user_id[:10]}...")
        print(f"✅ Validator bootstrap complete. {registered_count} validators are registered.")

        # 2. Get an overview of the existing validator set
        print("\n🧪 2. Querying existing validator set summary...")
        initial_counts = get_validator_counts(validator_index_service)
        initial_active_list = get_active_validators(validator_index_service)
        total_validators = initial_counts.get("total_validators", 0)
        initial_active_count = initial_counts.get("active_validators", 0)

        print(f"   - Total validators found: {total_validators}")
        print(f"   - Active validators found: {initial_active_count}")
        assert total_validators > 0, "Test requires pre-existing validator data, but none found."
        assert initial_active_count > 0, "Test requires at least one active validator to run."

        # 3. Test queries on a single, existing validator
        print("\n🧪 3. Testing queries on a single existing validator...")
        validator_to_test_index = initial_active_list[0]
        print(f"   - Using validator index {validator_to_test_index} for tests.")

        validator_data = get_validator(validator_index_service, validator_to_test_index)
        assert validator_data is not None, f"Could not retrieve validator {validator_to_test_index}"
        print("   - get_validator(by_index): OK")

        user_id = validator_data.get("user_id")
        if user_id:
            validator_by_user = get_validator_by_user(validator_index_service, user_id)
            assert validator_by_user is not None
            print("   - get_validator_by_user: OK")

        pubkey = validator_data["pubkey"]
        validator_by_pubkey = get_validator_by_pubkey(validator_index_service, pubkey)
        assert validator_by_pubkey is not None
        print("   - get_validator_by_pubkey: OK")

        # 4. Test validator status update and count verification
        print("\n🧪 4. Testing validator status update...")
        print(f"   - Updating validator {validator_to_test_index} to '{ValidatorStatus.ACTIVE_EXITING.value}'...")
        updated = update_validator_status(validator_index_service, validator_to_test_index,
                                          ValidatorStatus.ACTIVE_EXITING.value)
        print(f"   - Update successful: {updated}")
        assert updated

        new_counts = get_validator_counts(validator_index_service)
        print(f"   - New counts: Total={new_counts['total_validators']}, Active={new_counts['active_validators']}")
        assert new_counts['active_validators'] == initial_active_count - 1
        print("   - Active validator count correctly decreased by 1.")

        print(
            f"   - Reverting status for validator {validator_to_test_index} to '{ValidatorStatus.ACTIVE_ONGOING.value}'...")
        reverted = update_validator_status(validator_index_service, validator_to_test_index,
                                           ValidatorStatus.ACTIVE_ONGOING.value)
        assert reverted
        final_counts = get_validator_counts(validator_index_service)
        assert final_counts['active_validators'] == initial_active_count
        print("   - Status reverted successfully.")

        # 5. Cleanup
        validator_index_service.close()
        print("\n✅ Service closed.")
        print("\n✅ Validator Public API Test Complete!")


    asyncio.run(run_tests())
