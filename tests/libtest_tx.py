#!/usr/bin/env python3
"""
libtest_tx.py -- test and usage example for the public Transaction API."""

import os
import sys
import asyncio
from typing import Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_config import dirs
from BachiCoin.api_public import tx_lib_api, wallet_lib_api, user_lib_api, mempool_lib_api, crypto_lib_api, blockchain_lib_api, crossmodule_lib_api
from tests.libtest_data import TRANSACTION_SCHEDULE


class TxApiTester:
    """A simple, sequential tester class for the Transaction API."""

    def __init__(self):
        self.tx_service = None
        self.wallet_service = None
        self.user_service = None
        self.mempool_service = None
        self.address_map: Dict[str, Dict[str, str]] = {}
        self.private_key_map: Dict[str, str] = {}
        self.signed_txs: List[Dict] = []
        self.total_tx_count = 0
        self.initial_tx_count = 0 # To store the count before the test runs
        self.node_context: Optional[crossmodule_lib_api.NodeContext] = None

    async def run_all_tests(self):
        """Runs all test methods in a defined sequence."""
        print("=" * 60)
        print("== Running BachiCoin Transaction API Integration Test & Cookbook ==")
        print("=" * 60)

        self.test_01_initialize_services()
        self.test_02_resolve_addresses_and_keys()
        self.test_03_create_and_sign_transactions()
        self.test_04_verify_creation_and_stats()
        self.test_05_list_and_search_transactions()
        self.test_06_get_transactions_by_address()
        await self.test_07_submit_to_mempool()

        print("\n" + "=" * 60)
        print("✅✅✅ All Transaction API tests passed successfully! ✅✅✅")
        print("=" * 60)

    def test_01_initialize_services(self):
        print("\n--- 1. Initializing Services ---")
        self.node_context = crossmodule_lib_api.NodeContext(node_dirs=dirs)

        blockchain_svc = blockchain_lib_api.create_blockchain_index_service(self.node_context)
        self.node_context.blockchain_service = blockchain_svc

        self.tx_service = tx_lib_api.create_tx_index_service(self.node_context)
        self.wallet_service = wallet_lib_api.create_wallet_index_service(self.node_context)
        self.user_service = user_lib_api.create_user_index_service(self.node_context)
        self.mempool_service = mempool_lib_api.create_mempool_index_service(self.node_context)
        
        self.node_context.tx_service = self.tx_service
        self.node_context.wallet_service = self.wallet_service
        self.node_context.user_service = self.user_service
        self.node_context.mempool_service = self.mempool_service

        # Get the initial state of the transaction index
        stats = tx_lib_api.get_tx_index_stats(self.tx_service)
        self.initial_tx_count = stats.get("total_transactions", 0)
        print(f"✅ Services initialized. Initial transaction count: {self.initial_tx_count}")


    def test_02_resolve_addresses_and_keys(self):
        print("\n--- 2. Resolving User Addresses and Private Keys ---")
        all_users = user_lib_api.list_users(self.user_service)
        
        for user_info in all_users:
            user_name_key = f"{user_info['first_name']} {user_info['last_name']}"
            self.address_map[user_name_key] = {}
            
            mnemonic_seed = user_info["email_registration"]
            key_manager = crypto_lib_api.create_key_manager(crypto_lib_api.generate_mnemonic_from_seed(mnemonic_seed))

            user_wallets = wallet_lib_api.list_wallets_by_user(self.wallet_service, user_info["user_id"])
            
            for i, wallet_data in enumerate(user_wallets):
                wallet_type_str = wallet_data["wallet_type"]
                full_wallet_data = wallet_lib_api.get_wallet(self.wallet_service, wallet_data["wallet_id"])
                address = full_wallet_data["addresses"]["eoa"]["address"]
                
                self.address_map[user_name_key][wallet_type_str] = address

                addresses_and_keys = crypto_lib_api.generate_crypto_addresses(key_manager, account_index=i)
                key_label = addresses_and_keys['eoa']['label']
                private_key = crypto_lib_api.get_private_key_hex(key_manager, key_label)
                
                if private_key:
                    self.private_key_map[address] = private_key
                else:
                    print(f"Warning: Private key is None for address {address} (label: {key_label}). Not added to map.")
            
            print(f"✅ Resolved addresses and keys for {user_name_key}.")

    def test_03_create_and_sign_transactions(self):
        print("\n--- 3. Creating and Signing Transactions ---")
        nonces: Dict[str, int] = {}
        fee_defaults = tx_lib_api.TxConfig.FEE_DEFAULTS
        self.signed_txs.clear()

        print(f"--- Processing transaction schedule ({len(TRANSACTION_SCHEDULE)} transactions) ---")
        for i, tx_template in enumerate(TRANSACTION_SCHEDULE):
            from_ref = tx_template.get("from_ref")
            to_ref = tx_template.get("to_ref")
            tx_type = tx_template.get("tx_type")

            from_address: Optional[str] = None
            to_address: Optional[str] = None
            calculated_nonce: Optional[int] = None

            if from_ref:
                from_address = self.address_map[from_ref["user"]][from_ref["wallet"]]
                calculated_nonce = nonces.get(from_address, 0)

            if to_ref:
                to_address = self.address_map[to_ref["user"]][to_ref["wallet"]]

            if tx_type in [tx_lib_api.TxType.STAKE.value, tx_lib_api.TxType.UNSTAKE.value]:
                if not to_address:
                    to_address = from_address

            if tx_type in [tx_lib_api.TxType.MINT.value, tx_lib_api.TxType.REWARD.value, tx_lib_api.TxType.SLASH.value]:
                calculated_nonce = None

            unsigned_tx = tx_lib_api.create_tx_with_index(
                service=self.tx_service,
                tx_data={
                    "amount": tx_template["amount"],
                    "tx_type": tx_type,
                    "memo": f"Test TX: {from_ref.get('user') if from_ref else 'N/A'} -> {to_ref.get('user') if to_ref else 'N/A'}",
                    **fee_defaults.get(tx_template["priority"], fee_defaults["standard"])
                },
                from_address=from_address,
                to_address=to_address,
                calculated_nonce=calculated_nonce
            )
            assert unsigned_tx, f"Failed to create transaction {i + 1}."

            tx_hash = tx_lib_api.create_canonical_tx_hash(unsigned_tx)

            signature: Optional[str] = None
            if from_address and from_address in self.private_key_map and tx_type not in [tx_lib_api.TxType.MINT.value, tx_lib_api.TxType.REWARD.value, tx_lib_api.TxType.SLASH.value]:
                private_key = self.private_key_map[from_address]
                signature = crypto_lib_api.sign_transaction(tx_hash, private_key)
            
            signed_tx = unsigned_tx.copy()
            signed_tx['tx_hash'] = tx_hash
            signed_tx['signature'] = signature

            success = tx_lib_api.save_signed_transaction(self.tx_service, signed_tx)
            assert success, f"Failed to save signed transaction {i+1}."

            self.signed_txs.append(signed_tx)
            if from_address and calculated_nonce is not None:
                nonces[from_address] = calculated_nonce + 1

        self.total_tx_count = len(self.signed_txs)
        print(f"✅ Successfully created, signed, and saved {self.total_tx_count} transactions.")

    def test_04_verify_creation_and_stats(self):
        print("\n--- 4. Verifying Creation with Index Stats ---")
        stats = tx_lib_api.get_tx_index_stats(self.tx_service)
        
        expected_count = self.initial_tx_count + self.total_tx_count
        assert stats["total_transactions"] == expected_count, \
            f"Expected {expected_count} transactions in stats (initial {self.initial_tx_count} + new {self.total_tx_count}), but found {stats['total_transactions']}."
        print(f"✅ get_tx_index_stats returned correct total: {stats['total_transactions']}.")

    def test_05_list_and_search_transactions(self):
        print("\n--- 5. Listing and Searching Transactions ---")
        # This test now correctly checks only the newly added transactions
        expected_burns = len([tx for tx in self.signed_txs if tx["tx_type"] == tx_lib_api.TxType.BURN.value])
        # We list all transactions and then filter, as the service might contain old ones
        all_txs = tx_lib_api.list_transactions(self.tx_service)
        
        # Filter the list to only include transactions created in this test run
        new_tx_hashes = {tx['tx_hash'] for tx in self.signed_txs}
        newly_added_txs = [tx for tx in all_txs if tx['tx_hash'] in new_tx_hashes]

        burns = [tx for tx in newly_added_txs if tx["tx_type"] == tx_lib_api.TxType.BURN.value]
        assert len(burns) == expected_burns, f"list_transactions returned incorrect count for new burns. Expected {expected_burns}, Got {len(burns)}."
        print(f"✅ list_transactions with filter 'burn' found {len(burns)} new results.")

        expected_mints = len([tx for tx in self.signed_txs if tx["tx_type"] == tx_lib_api.TxType.MINT.value])
        mints = [tx for tx in newly_added_txs if tx["tx_type"] == tx_lib_api.TxType.MINT.value]
        assert len(mints) == expected_mints, f"list_transactions returned incorrect count for new mints. Expected {expected_mints}, Got {len(mints)}."
        print(f"✅ list_transactions with filter 'mint' found {len(mints)} new results.")

        expected_stakes = len([tx for tx in self.signed_txs if tx["tx_type"] == tx_lib_api.TxType.STAKE.value])
        stakes = [tx for tx in newly_added_txs if tx["tx_type"] == tx_lib_api.TxType.STAKE.value]
        assert len(stakes) == expected_stakes, f"list_transactions returned incorrect count for new stakes. Expected {expected_stakes}, Got {len(stakes)}."
        print(f"✅ list_transactions with filter 'stake' found {len(stakes)} new results.")


    def test_06_get_transactions_by_address(self):
        print("\n--- 6. Getting Transactions by Address ---")
        ledger_mint_address = self.address_map["Ledger System"]["mint"]
        ledger_tx_history = tx_lib_api.get_transactions_by_address(self.tx_service, ledger_mint_address)

        # This assertion might be fragile if previous tests didn't use this address.
        # A better test would be to check if the number of sent transactions increased.
        assert ledger_tx_history["total_sent"] > 0, "Expected to find transactions sent from Ledger System's mint wallet."
        print(f"✅ get_transactions_by_address for Ledger System's mint wallet found {ledger_tx_history['total_sent']} sent txs.")

    async def test_07_submit_to_mempool(self):
        print("\n--- 7. Submitting All Signed Transactions to Mempool ---")
        submitted_count = 0
        for tx_data in self.signed_txs:
            if tx_data.get('signature') and tx_data.get('from_address'):
                tx_hash = await mempool_lib_api.submit_transaction(self.mempool_service, tx_data)
                assert tx_hash and tx_hash.startswith("0x"), f"Failed to submit tx {tx_data.get('tx_hash')} to mempool. Returned: {tx_hash}"
                submitted_count += 1
            else:
                print(f"   Skipping submission of unsigned/system transaction: {tx_data.get('tx_type')}")

        print(f"✅ Successfully submitted {submitted_count} user-signed transactions to the mempool.")

        status = mempool_lib_api.get_mempool_status(self.mempool_service)
        expected_mempool_count = len([tx for tx in self.signed_txs if tx.get('signature') and tx.get('from_address')])
        assert status['total_transactions'] == expected_mempool_count, \
            f"Expected {expected_mempool_count} in mempool, but found {status['total_transactions']}"
        print(f"✅ Mempool status verified. Total pending: {status['total_transactions']}")


if __name__ == "__main__":
    tester = TxApiTester()
    asyncio.run(tester.run_all_tests())
