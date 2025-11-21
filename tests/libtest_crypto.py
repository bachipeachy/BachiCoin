#!/usr/bin/env python3
"""
libtest_crypto.py: A "Cookbook" for the BachiCoin Crypto Library API.

This script serves as both a sequential integration test and a set of clear,
runnable examples for using the functions in `crypto_lib_api.py`.
"""

import os
import sys

# Ensure the source directory is in the path to find the BachiCoin module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Import the public API functions to be tested
from BachiCoin.api_public import crypto_lib_api as api

# A known mnemonic for deterministic testing, used throughout the cookbook.
TEST_MNEMONIC = "legal winner thank year wave sausage worth useful legal winner thank yellow"


class CryptoApiCookbook:
    """Encapsulates all test cases, which also serve as usage examples."""

    def run_all_tests(self):
        """Runs all test methods in a defined order."""
        print("=== Running BachiCoin Crypto API Cookbook and Test Suite ===")

        test_methods = sorted([
            method_name for method_name in dir(self)
            if callable(getattr(self, method_name)) and method_name.startswith("test_")
        ])

        for method_name in test_methods:
            test_method = getattr(self, method_name)
            print(f"\n--- Running: {method_name} ---")
            test_method()

        print("\n✅✅✅ All examples ran successfully! ✅✅✅")

    def test_01_key_manager_creation(self):
        """Cookbook: How to create and initialize the KeyManager."""
        # Example 1: Create a new manager with a randomly generated mnemonic.
        manager1 = api.create_key_manager()
        assert manager1 is not None and api.get_mnemonic(manager1) is not None
        print("✅ Example 1: Created a new KeyManager with a random mnemonic.")

        # Example 2: Create a manager from a known, existing mnemonic for deterministic keys.
        manager2 = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        assert api.get_mnemonic(manager2) == TEST_MNEMONIC
        print("✅ Example 2: Created a KeyManager from a known mnemonic.")

        # Example 3: Create a watch-only manager that cannot handle private keys.
        manager_wo = api.create_key_manager(watch_only=True)
        assert manager_wo.watch_only is True
        try:
            api.derive_key(manager_wo)
            assert False, "Watch-only manager should not allow private key operations."
        except api.KeyManagerError:
            pass
        print("✅ Example 3: Created a watch-only manager which correctly restricts private key access.")

    def test_02_hd_key_derivation(self):
        """Cookbook: How to derive Hierarchical Deterministic (HD) keys."""
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)

        # Example 1: Derive a key sequentially. The manager finds the next available index.
        label1 = api.derive_key(manager, label="hd_key_0")
        key_info1 = manager.get_key_by_label(label1)
        assert label1 in api.list_keys(manager) and key_info1['path'] == "m/44'/66'/0'/0/0"
        print(f"✅ Example 1: Derived a key at the next sequential path: {key_info1['path']}")

        # Example 2: Derive a second key to show the index increments automatically.
        label2 = api.derive_key(manager, label="hd_key_1")
        key_info2 = manager.get_key_by_label(label2)
        assert key_info1['path'] != key_info2['path'] and key_info2['path'] == "m/44'/66'/0'/0/1"
        print(f"✅ Example 2: Derived a second key, index incremented to: {key_info2['path']}")

        # Example 3: Derive a key at a specific, non-sequential path.
        path = "m/44'/66'/0'/0/100"
        label3 = api.derive_key(manager, path=path, label="specific_path_key")
        key_info3 = manager.get_key_by_label(label3)
        assert key_info3['path'] == path
        print(f"✅ Example 3: Derived a key at a specific custom path: {path}")

    def test_03_der_signing(self):
        """Cookbook: How to create a standard, non-recoverable (DER) signature."""
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        label = api.derive_key(manager, label="der_signing_key")
        message = b"This is a test message for standard DER signing."

        # Sign the message. This signature can be verified but cannot be used to find the signer.
        signature = api.sign_message_der(manager, message, label)
        assert isinstance(signature, str)
        print(f"✅ Message signed to produce a non-recoverable DER signature.")

        # Verify the signature with the correct public key.
        is_valid = api.verify(manager, message, signature, label)
        assert is_valid is True
        print("✅ DER signature successfully verified with the correct key.")

    def test_04_address_generation(self):
        """Cookbook: How to generate blockchain addresses."""
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        label = api.derive_key(manager, label="address_key")

        # Example 1: Generate a Bitcoin-style (P2PKH) address.
        btc_address = api.get_address(manager, label, eth_format=False)
        assert btc_address.startswith('1')
        print(f"✅ Example 1: Generated a Bitcoin-style address: {btc_address}")

        # Example 2: Generate an Ethereum-style (EOA) address.
        eth_address = api.get_address(manager, label, eth_format=True)
        assert eth_address.startswith('0x') and len(eth_address) == 42
        print(f"✅ Example 2: Generated an Ethereum-style address: {eth_address}")

        # Example 3: Verify that address generation is deterministic for a given mnemonic.
        manager2 = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        label2 = api.derive_key(manager2, label="address_key")
        eth_address2 = api.get_address(manager2, label2, eth_format=True)
        assert eth_address == eth_address2
        print("✅ Example 3: Address generation is deterministic.")

    def test_05_import_export(self):
        """Cookbook: How to export and import all keys from a KeyManager."""
        manager1 = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        api.derive_key(manager1, label="hd_key_to_export")

        # Export all keys to a serializable dictionary.
        exported_data = api.export_keys(manager1)
        assert "hd_key_to_export" in exported_data
        print("✅ Keys successfully exported to a dictionary.")

        # Import the data into a new, empty manager.
        manager2 = api.create_key_manager()
        api.import_keys(manager2, exported_data)
        assert sorted(api.list_keys(manager1)) == sorted(api.list_keys(manager2))
        print("✅ Keys successfully imported into a new manager.")

        # Verify that the imported key is fully functional.
        message = b"testing imported keys"
        signature = api.sign_message_der(manager2, message, "hd_key_to_export")
        is_valid = api.verify(manager2, message, signature, "hd_key_to_export")
        assert is_valid is True
        print("✅ Imported key is fully functional for signing and verification.")

    def test_06_hybrid_address_generation(self):
        """Cookbook: How to generate crypto addresses for a user account."""
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)

        # This function derives keys based on a standard path for a user account index.
        addresses = api.generate_crypto_addresses(manager, account_index=0)
        assert "eoa" in addresses and addresses["eoa"]["address"].startswith("0x")
        print(f"✅ Generated hybrid addresses for account 0: EOA={addresses['eoa']['address']}")

    def test_07_extended_keys(self):
        """Cookbook: How to get extended public (xpub) and private (xprv) keys."""
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        path = "m/44'/66'/0'"

        xpub = api.get_xpub_by_path(manager, path)
        xprv = api.get_xprv_by_path(manager, path)

        assert xpub.startswith("xpub") and xprv.startswith("xprv")
        print(f"✅ Generated xpub and xprv for path '{path}'.")

    def test_08_deterministic_mnemonic_generation(self):
        """Cookbook: How to deterministically generate a mnemonic from a string."""
        # This is useful for creating predictable test wallets from a simple seed phrase.
        seed_phrase_1 = "bachi-coin-test-wallet-1"
        mnemonic_1 = api.generate_mnemonic_from_seed(seed_phrase_1)
        assert api.validate_mnemonic(mnemonic_1)
        print(f"✅ Generated a deterministic mnemonic from '{seed_phrase_1}'.")

        # Verify that the same seed phrase always produces the same mnemonic.
        mnemonic_2 = api.generate_mnemonic_from_seed(seed_phrase_1)
        assert mnemonic_1 == mnemonic_2
        print("✅ Mnemonic generation from seed is deterministic.")

    def test_09_transaction_signing_cookbook(self):
        """Cookbook: The complete workflow for signing and verifying a transaction."""
        # --- Step 1: Setup --- 
        # Create a key manager and derive a key for the user.
        manager = api.create_key_manager(seed_or_mnemonic=TEST_MNEMONIC)
        label = api.derive_key(manager, label="tx_signer_key")
        
        # Get the user's raw private key (hex) and their public address.
        # In a real app, the private key would be securely stored on the client.
        private_key_hex = api.get_private_key_hex(manager, label)
        original_address = api.get_address(manager, label, eth_format=True)
        print("Step 1: Key and address prepared for the user.")

        # --- Step 2: Create and Hash the Transaction --- 
        # A transaction is simulated as a simple byte string here.
        # In a real app, this would be a structured, serialized transaction object.
        transaction_data = b"a simulated transaction to be signed"
        tx_hash_bytes = api.hash_data(transaction_data)
        tx_hash_hex = "0x" + tx_hash_bytes.hex()
        print("Step 2: Transaction data has been hashed.")

        # --- Step 3: Sign the Hash --- 
        # The client signs the transaction hash with their private key.
        # This produces a recoverable signature.
        signature_hex = api.sign_transaction(tx_hash_hex, private_key_hex)
        assert signature_hex.startswith("0x") and len(signature_hex) == 132
        print("Step 3: Transaction hash signed by the client.")

        # --- Step 4: Verify the Signature (on a node/server) --- 
        # A node receives the transaction data, hash, and signature.
        # It recovers the public key from the signature to identify the signer.
        recovered_pub_key = api.recover_public_key(tx_hash_bytes, signature_hex)
        assert recovered_pub_key is not None
        print("Step 4: Server successfully recovered the public key from the signature.")

        # --- Step 5: Verify the Signer's Address --- 
        # The node converts the recovered public key to an address.
        recovered_address = api.public_key_to_address(recovered_pub_key)
        
        # The recovered address must match the claimed sender's address.
        assert recovered_address.lower() == original_address.lower()
        print("Step 5: Verification successful! Recovered address matches the original sender.")


if __name__ == "__main__":
    cookbook = CryptoApiCookbook()
    cookbook.run_all_tests()
