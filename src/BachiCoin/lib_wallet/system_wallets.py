#!/usr/bin/env python3
"""system_wallets.py - This script handles the creation of essential system wallets."""

from typing import List, Dict

from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_wallet.wallet_config import WalletType
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_crypto.key_manager import KeyManager


def create_system_wallets(
        wallet_service: WalletIndexService,
        system_user_ids: Dict[str, str]
) -> Dict[str, str]:
    """Creates the standard system wallets for the Ledger System and Genesis User, returning a dictionary of wallet IDs."""
    print("\n--- Bootstrapping System Wallets ---")
    created_wallet_ids = {}

    # --- Create wallets for Ledger System ---
    ledger_system_id = system_user_ids["ledger_system"]
    existing_ledger_wallets = {w.get("wallet_type"): w for w in wallet_service.list_wallets_by_user(ledger_system_id)}
    ledger_key_manager = KeyManager(seed_or_mnemonic=HdWallet.generate_mnemonic_from_seed("ledger.system@bachicoin.org"))

    for wallet_type in [WalletType.MINT, WalletType.BURN, WalletType.POOL]:
        if wallet_type.value in existing_ledger_wallets:
            print(f"🟡 Ledger System wallet '{wallet_type.value}' already exists. Skipping.")
            created_wallet_ids[f"ledger_system_{wallet_type.value.lower()}"] = existing_ledger_wallets[wallet_type.value]["wallet_id"]
            continue

        account_index = len(existing_ledger_wallets) + len(created_wallet_ids)
        addresses = ledger_key_manager.generate_crypto_addresses("BACHI", "testnet", account_index)

        wallet_data = {
            "name": f"Ledger System {wallet_type.value.capitalize()} Wallet",
            "wallet_type": wallet_type.value,
            "network": "testnet",
            "currency": "BACHI",
        }

        wallet_id = wallet_service.create_wallet_with_index(ledger_system_id, wallet_data, addresses)
        assert wallet_id, f"Failed to create {wallet_type.value} wallet for Ledger System."
        created_wallet_ids[f"ledger_system_{wallet_type.value.lower()}"] = wallet_id
        print(f"✅ Created '{wallet_type.value}' wallet for Ledger System with ID: {wallet_id}")

    # --- Create wallets for Genesis User ---
    genesis_user_id = system_user_ids["genesis_user"]
    existing_genesis_wallets = {w.get("wallet_type"): w for w in wallet_service.list_wallets_by_user(genesis_user_id)}
    genesis_key_manager = KeyManager(seed_or_mnemonic=HdWallet.generate_mnemonic_from_seed("genesis.user@bachicoin.org"))

    for wallet_type in [WalletType.PRIVATE, WalletType.BUSINESS]:
        if wallet_type.value in existing_genesis_wallets:
            print(f"🟡 Genesis User wallet '{wallet_type.value}' already exists. Skipping.")
            created_wallet_ids[f"genesis_user_{wallet_type.value.lower()}"] = existing_genesis_wallets[wallet_type.value]["wallet_id"]
            continue

        account_index = len(existing_genesis_wallets) + len(created_wallet_ids)
        addresses = genesis_key_manager.generate_crypto_addresses("BACHI", "testnet", account_index)

        wallet_data = {
            "name": f"Genesis User {wallet_type.value.capitalize()} Wallet",
            "wallet_type": wallet_type.value,
            "network": "testnet",
            "currency": "BACHI",
        }

        wallet_id = wallet_service.create_wallet_with_index(genesis_user_id, wallet_data, addresses)
        assert wallet_id, f"Failed to create {wallet_type.value} wallet for Genesis User."
        created_wallet_ids[f"genesis_user_{wallet_type.value.lower()}"] = wallet_id
        print(f"✅ Created '{wallet_type.value}' wallet for Genesis User with ID: {wallet_id}")

    return created_wallet_ids


if __name__ == "__main__":
    from tests.test_config import dirs
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
    from BachiCoin.lib_user.system_users import create_system_users

    u_service = UserServiceFactory.create_user_index_service(dirs)
    w_service = WalletServiceFactory.create_wallet_index_service(dirs, user_service=u_service)
    
    # First, ensure system users exist
    system_user_ids = create_system_users(u_service)
    
    # Then, create their wallets
    create_system_wallets(w_service, system_user_ids)
    print("\n--- System wallets bootstrap process complete. ---")
