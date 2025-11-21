#!/usr/bin/env python3
"""user_wallet_setup.py  -- creation of standard wallets for a given user."""

import asyncio
from typing import Dict
from pathlib import Path
import sys

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_wallet.wallet_config import WalletType
from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_crypto.key_manager import KeyManager
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


def create_user_wallets(
        node_context: NodeContext,
        user_id: str,
        passphrase_seed: str = None
) -> Dict[str, str]:
    """Creates the standard PRIVATE and BUSINESS wallets for a pre-existing user."""
    print(f"--- Running Wallet Setup for User ID: {user_id} ---")
    # Use attribute access on the NodeContext object
    user_service = node_context.user_service
    wallet_service = node_context.wallet_service
    network = node_context.network
    currency = node_context.currency

    # Look up the user record to get their email and name.
    all_users = user_service.list_users()
    user_record = next((u for u in all_users if u['user_id'] == user_id), None)

    if not user_record:
        raise ValueError(f"User with ID {user_id} not found on the specified node.")

    user_name_key = user_record.get('name', f"{user_record['first_name']} {user_record['last_name']}")
    email_address = user_record["email_registration"]
    print(f"Found user '{user_name_key}' with email '{email_address}'")

    # Determine the seed for key generation.
    if passphrase_seed:
        seed_for_keys = passphrase_seed
        print("  -> Using provided passphrase to seed key generation.")
    else:
        print("  ⚠️  Passphrase seed not provided. Defaulting to user's registered email for deterministic key generation.")
        seed_for_keys = email_address

    # Deterministically generate the KeyManager from the seed.
    key_manager = KeyManager(
        seed_or_mnemonic=HdWallet.generate_mnemonic_from_seed(seed_for_keys)
    )

    public_addresses = {}

    # Loop through the standard wallet types and create each one.
    for i, wallet_type in enumerate([WalletType.PRIVATE, WalletType.BUSINESS]):
        print(f"  -> Creating '{wallet_type.value}' wallet...")
        addresses = key_manager.generate_crypto_addresses(
            currency, network, i
        )

        wallet_data = {
            "name": f"{user_record['first_name']}'s {wallet_type.value.capitalize()} Wallet",
            "wallet_type": wallet_type.value
        }

        wallet_service.create_wallet_with_index(user_id, wallet_data, addresses)

        address_key = f"{user_name_key}_{wallet_type.value.lower()}"
        public_address = addresses['eoa']['address']
        public_addresses[address_key] = public_address
        print(f"  ✅ Created wallet with address: {public_address}")

    return public_addresses


if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from tests.test_config import all_node_dirs
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
    from BachiCoin.lib_user.user_setup import create_user

    @with_dirs
    async def main_smoke_test(node_dirs: Dirs):
        """Smoke test for the create_user_wallets function."""
        print("=" * 70)
        print("🚀 Starting Smoke Test for user_wallet_setup.py")
        print("=" * 70)

        # 1. Create services first.
        user_service = UserServiceFactory.create_user_index_service(node_dirs)
        wallet_service = WalletServiceFactory.create_wallet_index_service(node_dirs, user_service=user_service)

        # 2. Create a NodeContext instance.
        node_context = NodeContext.from_dirs(node_dirs)
        node_context.user_service = user_service
        node_context.wallet_service = wallet_service
        node_context.network = "testnet"
        node_context.currency = "BACHI"
        
        print("--- Minimal node context created for test ---")

        # 3. SETUP: Create a new user first.
        gomer_profile = {"first_name": "Gomer", "last_name": "Adams"}
        new_user_id = create_user(node_context, gomer_profile)
        print(f"--- Setup complete: Created user {new_user_id} ---\\n")

        # 4. EXECUTION: Call the function under test.
        created_addresses = create_user_wallets(node_context, new_user_id)

        # 5. VERIFICATION.
        print("\\n--- Verifying wallet creation ---")
        assert len(created_addresses) == 2
        assert "Gomer Adams_private" in created_addresses

        # Verify persistence by checking the service
        user_wallets = node_context.wallet_service.list_wallets_by_user(new_user_id)
        assert len(user_wallets) == 2

        print("✅ Verification PASSED.")
        print("=" * 70)

    asyncio.run(main_smoke_test(all_node_dirs[0]))
