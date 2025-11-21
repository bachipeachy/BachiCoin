#!/usr/bin/env python3
"""test_user_lib.py -- tests for the public User API."""

import os
import sys
from typing import Dict

# Ensure the source directory is in the path to find the BachiCoin module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from BachiCoin.api_public import user_lib_api, bootstrap_lib_api
from libtest_data import REGULAR_USERS
from tests.test_config import dirs

class UserApiTester:
    """A simple, sequential tester class for the User API."""

    def __init__(self):
        self.user_index_service = None
        self.test_user_ids: Dict[str, str] = {}

    def run_all_tests(self):
        """Runs all test methods in a defined sequence."""
        print("=" * 60)
        print("=== Running BachiCoin User API Integration Test & Cookbook ===")
        print("=" * 60)

        # The sequence of tests is important as they build on each other
        self.test_01_initialize_services()
        self.test_02_create_system_users()
        self.test_03_create_test_users()
        self.test_04_read_and_list_users()
        self.test_05_update_and_cleanup()
        self.test_06_delete_user()

        print("\n" + "=" * 60)
        print("✅✅✅ All User API tests passed successfully! ✅✅✅")
        print("=" * 60)
        print(f"\nPersistent user data has been created/verified in: {dirs.user}")

    def test_01_initialize_services(self):
        print("\n--- 1. Initializing Services ---")
        self.user_index_service = user_lib_api.create_user_index_service(dirs)
        assert self.user_index_service is not None, "Service creation failed."
        print("✅ UserIndexService initialized.")

    def test_02_create_system_users(self):
        print("\n--- 2. Creating System Users ---")
        system_user_ids = user_lib_api.create_system_users(self.user_index_service)
        assert system_user_ids and "ledger_system" in system_user_ids and "genesis_user" in system_user_ids
        self.test_user_ids['ledger_system'] = system_user_ids['ledger_system']
        self.test_user_ids['genesis_user'] = system_user_ids['genesis_user']
        print(f"✅ System users created or verified. Ledger ID: {system_user_ids['ledger_system']}, Genesis ID: {system_user_ids['genesis_user']}")

    def test_03_create_test_users(self):
        print("\n--- 3. Creating Test Users (Idempotent) ---")

        USERS = [*bootstrap_lib_api.BOOTSTRAP_USERS, *REGULAR_USERS]
        for user_def in USERS:
            if user_def["name"] in ["Ledger System", "Genesis User"]: continue

            key = user_def["name"].split(" ")[0].lower()
            email = f"{user_def['email_prefix']}@bachicoin.org"

            search_results = user_lib_api.search_users(self.user_index_service, email)
            existing_user = next((u for u in search_results if u.get('email_current') == email), None)

            if existing_user:
                print(f"⚠️ User with email '{email}' already exists. Verifying.")
                self.test_user_ids[key] = existing_user['user_id']
                continue

            first_name, last_name = user_def["name"].split(" ", 1)
            user_payload = {
                "first_name": first_name,
                "last_name": last_name,
                "email_registration": email,
            }

            result = user_lib_api.create_user_with_index(self.user_index_service, user_payload)
            assert result and result.get("user_id"), f"Creation failed for {key}"
            user_id = result["user_id"]
            self.test_user_ids[key] = user_id
            print(f"✅ User '{user_def['name']}' created. User ID: {user_id}")

    def test_04_read_and_list_users(self):
        print("\n--- 4. Reading and Listing User Data ---")
        all_users = user_lib_api.list_users(self.user_index_service)
        # 2 system users + 4 validators + 4 regular users
        assert len(all_users) >= 10, f"list_all_users should return at least 10 users, but found {len(all_users)}."
        print(f"✅ list_all_users returned {len(all_users)} users.")

        gomer_id = self.test_user_ids["gomer"]
        gomer_summary = user_lib_api.get_user_summary(self.user_index_service, gomer_id)
        assert gomer_summary and gomer_summary["first_name"] == "Gomer"
        print(f"✅ get_user_summary for Gomer successful: {gomer_summary['first_name']}")

    def test_05_update_and_cleanup(self):
        print("\n--- 5. Updating User Record and Cleaning Up ---")
        liam_id = self.test_user_ids["liam"]

        # 1. Add mock wallets for testing purposes
        user_lib_api.add_wallet_to_user(self.user_index_service, liam_id, "W1000")
        user_lib_api.add_wallet_to_user(self.user_index_service, liam_id, "W500")
        liam_summary = user_lib_api.get_user_summary(self.user_index_service, liam_id)
        assert "W1000" in liam_summary["wallet_ids"]
        print("✅ add_wallet_to_user successful for Liam.")

        update_success = user_lib_api.update_user_balance(self.user_index_service, liam_id, 0)
        assert update_success, "Direct balance update failed."
        liam_summary_after = user_lib_api.get_user_summary(self.user_index_service, liam_id)
        assert liam_summary_after["total_balance"] == 0
        print("✅ Direct balance update successful. Liam's balance is now 0")

        print("Cleaning up mock wallet IDs from Liam's record...")
        user_lib_api.remove_wallet_from_user(self.user_index_service, liam_id, "W1000")
        user_lib_api.remove_wallet_from_user(self.user_index_service, liam_id, "W500")
        liam_final_summary = user_lib_api.get_user_summary(self.user_index_service, liam_id)
        assert "W1000" not in liam_final_summary["wallet_ids"]
        print("✅ Mock wallet IDs cleaned up successfully.")

    def test_06_delete_user(self):
        print("\n--- 6. Deleting a User ---")
        liam_id = self.test_user_ids["liam"]
        liam_summary = user_lib_api.get_user_summary(self.user_index_service, liam_id)
        if liam_summary.get("wallet_ids"):
            try:
                user_lib_api.delete_user_with_index(self.user_index_service, liam_id)
                assert False, "Should not be able to delete a user with wallets."
            except AssertionError as e:
                print(f"✅ Correctly prevented deletion of user with wallets: {e}")
        else:
            print("🟡 Skipping deletion test for user with wallets, as they have none.")

        temp_user_payload = {
            "first_name": "David", "last_name": "Disposable", "email_registration": "david@bachicoin.org"
        }
        result = user_lib_api.create_user_with_index(self.user_index_service, temp_user_payload)
        assert result and result.get("user_id"), "Creation of temporary user failed."
        david_id = result["user_id"]
        print(f"✅ Created temporary user 'David' for deletion test. User ID: {david_id}")

        delete_success = user_lib_api.delete_user_with_index(self.user_index_service, david_id)
        assert delete_success, "Temporary user deletion failed."
        assert user_lib_api.get_user_summary(self.user_index_service, david_id) is None
        print("✅ Temporary user 'David' deleted successfully.")


if __name__ == "__main__":
    tester = UserApiTester()
    tester.run_all_tests()
