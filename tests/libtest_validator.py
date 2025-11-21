#!/usr/bin/env python3
"""test_validator_lib.py - functional test for the Validator lib API. with pre-staged test data"""

import asyncio
from pathlib import Path

from BachiCoin.api_public import user_lib_api, wallet_lib_api, validator_lib_api
from tests.test_config import dirs

async def run_validator_tests():
    """Main async function to run the validator functional tests."""
    print("=== Validator Public API Functional Test (using existing data) ===")

    print("\n🧪 1. Creating services and loading existing data...")
    user_service = user_lib_api.create_user_index_service(dirs)
    wallet_service = wallet_lib_api.create_wallet_index_service(dirs)
    validator_service = validator_lib_api.create_validator_index_service(dirs)
    print("✅ All services created.")

    print("\n🧪 2. Bootstrapping validators from existing users...")
    all_users = user_lib_api.list_users(user_service)
    # We want to exclude system-level users from becoming validators in this test.
    # These are the 'Genesis User' and the 'Ledger System' user.
    system_user_types = {user_lib_api.UserType.GENESIS.value, user_lib_api.UserType.LEDGER.value}
    regular_users = [u for u in all_users if u.get("user_type") not in system_user_types]
    registered_count = 0
    for user in regular_users:
        user_id = user["user_id"]
        if validator_lib_api.get_validator_by_user(validator_service, user_id):
            print(f"   - User {user_id[:10]}... is already a validator. Skipping.")
            registered_count += 1
            continue

        user_wallets = wallet_lib_api.list_wallets_by_user(wallet_service, user_id)
        if not user_wallets:
            print(f"   - ⚠️  User {user_id[:10]}... has no wallets. Cannot register.")
            continue

        wallet_id_to_use = user_wallets[0]["wallet_id"]
        print(f"   - Registering user {user_id[:10]}... with wallet {wallet_id_to_use[:10]}...")

        validator_index = validator_lib_api.register_validator(
            validator_service, user_id, wallet_id_to_use
        )
        if validator_index is not None:
            print(f"   - ✅ Successfully registered validator with index {validator_index}.")
            registered_count += 1
        else:
            print(f"   - ❌ Failed to register validator for user {user_id[:10]}...")
    print(f"✅ Validator bootstrap complete. {registered_count} validators are registered.")
    assert registered_count > 0, "Test requires at least one validator to be registered."

    print("\n🧪 3. Querying existing validator set summary...")
    initial_counts = validator_lib_api.get_validator_counts(validator_service)
    initial_active_list = validator_lib_api.get_active_validators(validator_service)
    total_validators = initial_counts.get("total_validators", 0)
    initial_active_count = initial_counts.get("active_validators", 0)

    print(f"   - Total validators found: {total_validators}")
    print(f"   - Active validators found: {initial_active_count}")
    assert total_validators > 0, "Test requires validator data, but none found."
    assert initial_active_count > 0, "Test requires at least one active validator."

    print("\n🧪 4. Testing queries on a single existing validator...")
    validator_to_test_index = initial_active_list[0]
    print(f"   - Using validator index {validator_to_test_index} for tests.")

    validator_data = validator_lib_api.get_validator(validator_service, validator_to_test_index)
    assert validator_data is not None, f"Could not retrieve validator {validator_to_test_index}"
    print("   - get_validator(by_index): OK")

    user_id = validator_data.get("user_id")
    if user_id:
        validator_by_user = validator_lib_api.get_validator_by_user(validator_service, user_id)
        assert validator_by_user is not None
        print("   - get_validator_by_user: OK")

    pubkey = validator_data["pubkey"]
    validator_by_pubkey = validator_lib_api.get_validator_by_pubkey(validator_service, pubkey)
    assert validator_by_pubkey is not None
    print("   - get_validator_by_pubkey: OK")

    print("\n🧪 5. Testing validator status update...")
    print(f"   - Updating validator {validator_to_test_index} to '{validator_lib_api.ValidatorStatus.ACTIVE_EXITING.value}'...")
    updated = validator_lib_api.update_validator_status(
        validator_service, validator_to_test_index, validator_lib_api.ValidatorStatus.ACTIVE_EXITING.value
    )
    print(f"   - Update successful: {updated}")
    assert updated

    new_counts = validator_lib_api.get_validator_counts(validator_service)
    print(f"   - New counts: Total={new_counts['total_validators']}, Active={new_counts['active_validators']}")
    assert new_counts['active_validators'] == initial_active_count - 1
    print("   - ✅ Active validator count correctly decreased by 1.")

    print(f"   - Reverting status for validator {validator_to_test_index} to '{validator_lib_api.ValidatorStatus.ACTIVE_ONGOING.value}'...")
    reverted = validator_lib_api.update_validator_status(
        validator_service, validator_to_test_index, validator_lib_api.ValidatorStatus.ACTIVE_ONGOING.value
    )
    assert reverted
    final_counts = validator_lib_api.get_validator_counts(validator_service)
    assert final_counts['active_validators'] == initial_active_count
    print("   - ✅ Status reverted successfully.")

    validator_service.close()
    print("\n✅ Service closed.")


if __name__ == "__main__":
    print("### Running Validator Test ###")
    asyncio.run(run_validator_tests())
    print("\n### Test Complete ###")
