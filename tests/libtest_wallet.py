#!/usr/bin/env python3
"""test_wallet_lib.py - A comprehensive test and usage example for the public Wallet API."""

import os
import sys
from typing import Dict

# Ensure the source directory is in the path to find the BachiCoin module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from BachiCoin.api_public import wallet_lib_api, user_lib_api, crypto_lib_api, generate_id_api
from tests.test_config import dirs


# Define the users we expect to find and create wallets for
USER_WALLET_TYPES = [wallet_lib_api.WalletType.PRIVATE, wallet_lib_api.WalletType.BUSINESS]


class WalletApiTester:
    """A simple, sequential tester class for the Wallet API."""

    def __init__(self):
        self.wallet_index_service = None
        self.user_index_service = None
        self.test_user_ids: Dict[str, str] = {}
        self.test_user_emails: Dict[str, str] = {}
        self.test_wallet_ids: Dict[str, str] = {}

    def run_all_tests(self):
        """Runs all test methods in a defined sequence."""
        print("=" * 60)
        print("== Running BachiCoin Wallet API Integration Test & Cookbook ==")
        print("=" * 60)

        self.test_01_initialize_services()
        self.test_02_find_system_users_and_create_wallets()
        self.test_03_create_test_users()
        self.test_04_create_user_wallets()
        self.test_05_read_and_list_wallets()
        self.test_06_update_and_delete()

        print("\n" + "=" * 60)
        print("✅✅✅ All Wallet API tests passed successfully! ✅✅✅")
        print("=" * 60)
        print(f"\nPersistent wallet data has been created/verified in: {dirs.wallet}")

    def test_01_initialize_services(self):
        """--- Step 1: Initializing the Wallet Service ---"""
        print("\n--- 1. Initializing Services ---")

        self.user_index_service = user_lib_api.create_user_index_service(dirs)
        self.wallet_index_service = wallet_lib_api.create_wallet_index_service(dirs, user_service=self.user_index_service)

        assert self.wallet_index_service is not None, "Wallet service creation failed."
        assert self.user_index_service is not None, "User service creation failed."
        print(f"✅ Wallet and User services initialized successfully.")

    def test_02_find_system_users_and_create_wallets(self):
        """--- Step 2: Find System Users and Create Their Wallets ---"""
        print("\n--- 2. Finding System Users & Creating Wallets (Idempotent) ---")
        all_users = user_lib_api.list_users(self.user_index_service)
        system_user_ids = {}

        for user in all_users:
            if user.get("user_type") == user_lib_api.UserType.GENESIS.value:
                system_user_ids['genesis_user'] = user['user_id']
                self.test_user_ids['Genesis User'] = user['user_id']
            elif user.get("user_type") == user_lib_api.UserType.LEDGER.value:
                system_user_ids['ledger_system'] = user['user_id']
                self.test_user_ids['Ledger System'] = user['user_id']

        assert "genesis_user" in system_user_ids, "Could not find the Genesis user."
        assert "ledger_system" in system_user_ids, "Could not find the Ledger System user."
        print(f"✅ Found Genesis User: {system_user_ids['genesis_user']}")
        print(f"✅ Found Ledger System User: {system_user_ids['ledger_system']}")

        created_wallet_ids = wallet_lib_api.create_system_wallets(self.wallet_index_service, system_user_ids)
        assert len(created_wallet_ids) >= 5, "Expected at least 5 system wallets to be created."
        print(f"✅ System wallets created or verified.")

    def test_03_create_test_users(self):
        """
        --- Step 3: Finding the Test Users ---
        Before creating wallets, we need to get the IDs of the users created
        by the user_lib_api test script.
        """
        print("\n--- 3. Finding Test Users ---")
        all_users = user_lib_api.list_users(self.user_index_service)
        assert len(all_users) >= 10, f"Expected at least 10 users, but found {len(all_users)}."

        # Find and store the ID for all test users, using a unique name
        self.test_user_ids.clear()
        self.test_user_emails.clear()

        for user in all_users:
            user_id = user['user_id']
            user_email = user['email_registration']
            first_name = user.get("first_name")
            last_name = user.get("last_name", "")
            
            # Create a unique name, e.g., "Staker A", "Genesis User"
            unique_name = f"{first_name} {last_name}".strip()

            if first_name:
                self.test_user_ids[unique_name] = user_id
                self.test_user_emails[unique_name] = user_email
                print(f"✅ Found {unique_name}: {user_id}")

    def test_04_create_user_wallets(self):
        """
        --- Step 4: Creating Wallets for Regular Users ---
        This demonstrates creating specific types of wallets for our test users.
        The process is idempotent.
        """
        print("\n--- 4. Creating User Wallets (Idempotent) ---")

        test_user_names = [name for name in self.test_user_ids if name not in ['Ledger System', 'Genesis User']]
        for user_name in test_user_names:
            user_id = self.test_user_ids[user_name]
            user_email = self.test_user_emails[user_name]
            existing_wallets = {w.get("wallet_type"): w for w in
                                wallet_lib_api.list_wallets_by_user(self.wallet_index_service, user_id)}

            # Deterministically generate mnemonic and keys for this user
            mnemonic_seed = user_email # Use email as a deterministic seed
            mnemonic = crypto_lib_api.generate_mnemonic_from_seed(mnemonic_seed)
            key_manager = crypto_lib_api.create_key_manager(mnemonic)

            for i, wallet_type in enumerate(USER_WALLET_TYPES):
                key = f"{user_name}_{wallet_type.value}"
                
                # Derive a unique address for each wallet
                addresses_dict = crypto_lib_api.generate_crypto_addresses(key_manager, currency="BACHI", network="testnet", account_index=i)
                eoa_address = addresses_dict["eoa"]["address"]
                eoa_label = addresses_dict["eoa"]["label"]
                private_key = crypto_lib_api.get_private_key_hex(key_manager, eoa_label)

                if wallet_type.value in existing_wallets:
                    print(f"🟡 Wallet '{wallet_type.value}' already exists for {user_name}. Verifying.")
                    wallet_id = existing_wallets[wallet_type.value]['wallet_id']
                    # For idempotency, ensure the existing wallet_id matches the deterministic one
                    expected_wallet_id = generate_id_api.generate_hash_id("W", {
                        "user_id": user_id,
                        "wallet_type": wallet_type.value,
                        "name": f"{user_name}'s {wallet_type.value.capitalize()} Wallet"
                    })
                    assert wallet_id == expected_wallet_id, f"Existing wallet ID mismatch for {user_name}'s {wallet_type.value} wallet."
                    self.test_wallet_ids[key] = wallet_id
                else:
                    wallet_payload = {
                        "name": f"{user_name}'s {wallet_type.value.capitalize()} Wallet",
                        "wallet_type": wallet_type.value,
                    }
                    # Pass the generated addresses_dict
                    wallet_id = wallet_lib_api.create_wallet_with_index(self.wallet_index_service, user_id, wallet_payload, addresses_dict)
                    assert wallet_id, f"Creation failed for {user_name}'s {wallet_type.value} wallet."
                    self.test_wallet_ids[key] = wallet_id
                    print(f"✅ Created '{wallet_type.value}' wallet for {user_name}. ID: {wallet_id}")

    def test_05_read_and_list_wallets(self):
        """
        --- Step 5: Reading and Listing Wallets ---
        Demonstrates retrieving wallet data using the API.
        """
        print("\n--- 5. Reading and Listing Wallet Data ---")
        
        test_user_names = [name for name in self.test_user_ids if name not in ['Ledger System', 'Genesis User']]
        if not test_user_names:
            print("🟡 Skipping read/list test, no regular users found.")
            return
        
        user_name_to_test = test_user_names[0]
        user_id_to_test = self.test_user_ids[user_name_to_test]

        # 1. List all wallets for a user
        user_wallets = wallet_lib_api.list_wallets_by_user(self.wallet_index_service, user_id_to_test)
        assert len(user_wallets) == len(USER_WALLET_TYPES), f"{user_name_to_test} should have {len(USER_WALLET_TYPES)} wallets."
        print(f"✅ list_wallets_by_user for {user_name_to_test} returned {len(user_wallets)} wallets.")

        # 2. Get summary data for one wallet
        private_wallet_key = f"{user_name_to_test}_{wallet_lib_api.WalletType.PRIVATE.value}"
        private_wallet_id = self.test_wallet_ids[private_wallet_key]
        summary = wallet_lib_api.get_wallet_summary(self.wallet_index_service, private_wallet_id)
        expected_name = f"{user_name_to_test}'s {wallet_lib_api.WalletType.PRIVATE.value.capitalize()} Wallet"
        assert summary and summary["name"] == expected_name
        print(f"✅ get_wallet_summary successful: {summary['name']}, Balance: {summary['balance']}")

        # 3. Get full data for the same wallet
        full_data = wallet_lib_api.get_wallet(self.wallet_index_service, private_wallet_id)
        assert full_data and "addresses" in full_data
        print("✅ get_wallet successful (contains addresses and other details).")

    def test_06_update_and_delete(self):
        """
        --- Step 6: Updating and Deleting a Wallet ---
        Demonstrates modifying a wallet's state and the deletion process.
        Deletion is tested on a temporary wallet to maintain the desired final state.
        """
        print("\n--- 6. Updating and Deleting a Wallet ---")
        
        test_user_names = [name for name in self.test_user_ids if name not in ['Ledger System', 'Genesis User']]
        if len(test_user_names) < 2:
            print("🟡 Skipping update/delete test, requires at least 2 regular users.")
            return

        user_name_to_test = test_user_names[-1] # Use the last user for this test
        user_id_to_test = self.test_user_ids[user_name_to_test]
        user_email_to_test = self.test_user_emails[user_name_to_test]
        business_wallet_key = f"{user_name_to_test}_{wallet_lib_api.WalletType.BUSINESS.value}"
        business_wallet_id = self.test_wallet_ids[business_wallet_key]

        # 1. Update a wallet's balance
        print(f"Updating balance for {user_name_to_test}'s business wallet...")
        update_success = wallet_lib_api.update_wallet_balance(self.wallet_index_service, business_wallet_id, 0)
        assert update_success, "update_wallet_balance failed."
        summary_after = wallet_lib_api.get_wallet_summary(self.wallet_index_service, business_wallet_id)
        assert summary_after["balance"] == 0
        print("✅ update_wallet_balance successful. New balance is 0.")

        # 2. Create a temporary wallet for deletion test
        temp_wallet_payload = {"name": f"{user_name_to_test}'s Temp Wallet"}
        # Generate addresses for the temporary wallet
        mnemonic_seed = user_email_to_test + "_temp" # Use email + suffix for deterministic temp wallet
        mnemonic = crypto_lib_api.generate_mnemonic_from_seed(mnemonic_seed)
        key_manager = crypto_lib_api.create_key_manager(mnemonic)
        temp_addresses_dict = crypto_lib_api.generate_crypto_addresses(key_manager, currency="BACHI", network="testnet", account_index=99) # Use a high index for temp

        temp_wallet_id = wallet_lib_api.create_wallet_with_index(self.wallet_index_service, user_id_to_test, temp_wallet_payload, temp_addresses_dict)
        assert temp_wallet_id, "Creation of temporary wallet failed."
        print(f"✅ Created temporary wallet for deletion test. ID: {temp_wallet_id}")

        # 3. Delete the temporary wallet
        delete_success = wallet_lib_api.delete_wallet_with_index(self.wallet_index_service, temp_wallet_id)
        assert delete_success, "Temporary wallet deletion failed."
        assert wallet_lib_api.get_wallet_summary(self.wallet_index_service, temp_wallet_id) is None
        print("✅ Temporary wallet deleted successfully.")


if __name__ == "__main__":
    # Create an instance of the tester and run all test methods.
    tester = WalletApiTester()
    tester.run_all_tests()
