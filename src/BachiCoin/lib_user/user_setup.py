#!/usr/bin/env python3
"""user_setup.py - Component for handling the creation of a user account on a specific node."""

import asyncio
from typing import Dict
from pathlib import Path
import sys

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


def create_user(node_context: NodeContext, user_profile: Dict[str, str]) -> str:
    """Creates a single user account within a specific node's user_service."""

    print(f"--- Running User Setup for {user_profile['first_name']} {user_profile['last_name']} ---")
    # Use attribute access on the NodeContext object
    user_service = node_context.user_service

    # Prepare the user payload, creating a default email if not provided.
    email = user_profile.get("email_registration") or \
            f"{user_profile['first_name']}.{user_profile['last_name']}@bachicoin.org".lower()

    user_payload = {
        "first_name": user_profile["first_name"],
        "last_name": user_profile["last_name"],
        "email_registration": email,
        "user_type": user_profile.get("user_type", "testnet"),
    }

    # Call the user service to create the user with an index.
    creation_result = user_service.create_user_with_index(user_payload)
    user_id = creation_result.get("user_id")

    if not user_id:
        raise Exception(f"User creation failed for {user_payload['email_registration']}. Result: {creation_result}")

    print(f"✅ User '{user_payload['first_name']} {user_payload['last_name']}' created with ID: {user_id}")
    return user_id


if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from tests.test_config import all_node_dirs

    @with_dirs
    async def main_smoke_test(node_dirs: Dirs): # Dirs object is now injected by the decorator
        """Smoke test for the create_user function."""
        print("=" * 70)
        print("🚀 Starting Smoke Test for user_setup.py")
        print("=" * 70)

        # 1. Create the user service first using the factory directly
        user_service = UserServiceFactory.create_user_index_service(node_dirs)

        # 2. Create a NodeContext instance, populating only the necessary services for this test
        node_context = NodeContext.from_dirs(node_dirs)
        node_context.user_service = user_service
        
        print("--- Minimal node context created for test ---")

        # 3. Define a sample user profile for the test.
        gomer_profile = {
            "first_name": "Gomer",
            "last_name": "Adams",
        }

        # 4. Execute the create_user function.
        new_user_id = create_user(node_context, gomer_profile)

        # 5. Verification.
        print("\n--- Verifying user creation ---")
        assert new_user_id is not None
        assert new_user_id.startswith("U_")

        # Use the service from the context to verify
        all_users_list = node_context.user_service.list_users()
        found_user = any(user['user_id'] == new_user_id and user['first_name'] == 'Gomer' for user in all_users_list)

        assert found_user, f"Verification failed: User with ID {new_user_id} not found in user service."
        print(f"✅ Verification successful: Found user {new_user_id} in the user service.")

        print("\nNOTE: Test data remains in the standard test directory for inspection.")
        print("=" * 70)
        print("🎉 Smoke Test for user_setup.py PASSED")
        print("=" * 70)


    asyncio.run(main_smoke_test(all_node_dirs[0])) # Pass the dirs object to the decorated function
