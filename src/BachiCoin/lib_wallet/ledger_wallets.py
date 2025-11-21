#!/usr/bin/env python3
"""ledger_wallets.py - create of the three unique wallets (MINT, BURN, POOL) for the Ledger System"""

import asyncio
from typing import Dict
from pathlib import Path
import sys

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_wallet.wallet_config import WalletType
from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_crypto.key_manager import KeyManager
from BachiCoin.lib_crossmodule.dirs import with_dirs, Dirs


def create_ledger_wallets(
        node_context: NodeContext,
        ledger_system_user_id: str
) -> Dict[str, str]:
    """Creates the three special-purpose wallets for the Ledger System user."""
    print("\\n--- Bootstrapping Ledger System Wallets ---")
    # Use attribute access on the NodeContext object
    user_service = node_context.user_service
    wallet_service = node_context.wallet_service
    network = node_context.network
    currency = node_context.currency

    all_users = user_service.list_users()
    user_record = next((u for u in all_users if u['user_id'] == ledger_system_user_id), None)
    if not user_record:
        raise ValueError(f"Could not find Ledger System user with ID {ledger_system_user_id}")

    email_seed = user_record["email_registration"]
    key_manager = KeyManager(
        seed_or_mnemonic=HdWallet.generate_mnemonic_from_seed(email_seed)
    )

    public_addresses = {}
    system_wallet_types = [WalletType.MINT, WalletType.BURN, WalletType.POOL]

    for i, wallet_type in enumerate(system_wallet_types):
        addresses = key_manager.generate_crypto_addresses(
            currency, network, i
        )
        wallet_data = {
            "name": f"Ledger System {wallet_type.value.capitalize()} Wallet",
            "wallet_type": wallet_type.value,
        }
        wallet_id = wallet_service.create_wallet_with_index(ledger_system_user_id, wallet_data, addresses)
        assert wallet_id, f"Failed to create {wallet_type.value} wallet for Ledger System."

        address_key = f"Ledger System_{wallet_type.value.lower()}"
        public_address = addresses['eoa']['address']
        public_addresses[address_key] = public_address
        print(f"✅ Created '{wallet_type.value}' wallet for Ledger System with ID: {wallet_id}")

    return public_addresses


if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from tests.test_config import all_node_dirs
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
    from BachiCoin.lib_user.system_users import create_system_users

    @with_dirs
    async def main_smoke_test(node_dirs: Dirs):
        """Smoke test for the create_ledger_wallets function."""
        print("=" * 70)
        print("🚀 Starting Smoke Test for ledger_wallets.py")
        print("=" * 70)

        # 1. Create services first
        user_service = UserServiceFactory.create_user_index_service(node_dirs)
        wallet_service = WalletServiceFactory.create_wallet_index_service(node_dirs, user_service=user_service)

        # 2. Create a NodeContext instance
        node_context = NodeContext.from_dirs(node_dirs)
        node_context.user_service = user_service
        node_context.wallet_service = wallet_service
        node_context.network = "testnet"
        node_context.currency = "BACHI"
        
        print("--- Minimal node context created for test ---")

        # 3. SETUP: Create system users to get the Ledger System ID
        system_user_ids = create_system_users(user_service)
        ledger_id = system_user_ids.get("ledger_system")
        assert ledger_id, "Failed to get Ledger System user ID"
        print(f"--- Setup complete: Found Ledger System user {ledger_id} ---\n")

        # 4. EXECUTION: Call the function under test.
        address_map = create_ledger_wallets(node_context, ledger_id)

        # 5. VERIFICATION.
        print("\n--- Verifying wallet creation ---")
        assert len(address_map) == 3
        assert "Ledger System_mint" in address_map
        print("✅ Verification PASSED.")
        print("=" * 70)

    asyncio.run(main_smoke_test(all_node_dirs[0]))
