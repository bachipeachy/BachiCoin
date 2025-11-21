"""
bootstrap_utils.py - Generic, reusable utility functions for bootstrapping nodes.
"""
import asyncio
import shutil
from pathlib import Path
import sys
from typing import Dict, Any, List, Tuple, Optional

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_user.user_setup import create_user
from BachiCoin.lib_wallet.user_wallet_setup import create_user_wallets
from BachiCoin.lib_wallet.ledger_wallets import create_ledger_wallets
from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_crypto.key_manager import KeyManager

# Direct imports for service factories
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_mempool.mempool_service_factory import MempoolServiceFactory
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_proposer.proposer_service_factory import ProposerServiceFactory
from BachiCoin.lib_attestor.attestor_service_factory import AttestorServiceFactory
from BachiCoin.lib_finalizer.finalizer_service_factory import FinalizerServiceFactory


def get_maps_for_user_identities(node_context: NodeContext) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Scans all users known to a node_context, regenerates their keys and addresses
    in-memory, and returns a tuple of (address_map, private_key_map).
    This is a read-only operation that does not create new users or wallets.
    """
    address_map = {}
    private_key_map = {}

    all_users_on_node = node_context.user_service.list_users()
    for user in all_users_on_node:
        user_name_key = user.get('name', f"{user['first_name']} {user['last_name']}")
        seed_for_key_manager = user["email_registration"]
            
        key_manager = KeyManager(seed_or_mnemonic=HdWallet.generate_mnemonic_from_seed(seed_for_key_manager))
        user_wallets = node_context.wallet_service.list_wallets_by_user(user["user_id"])

        for i, wallet_data in enumerate(user_wallets):
            key_manager.generate_crypto_addresses(node_context.currency, node_context.network, i)
            
            address = wallet_data['addresses']['eoa']['address']
            label = wallet_data['addresses']['eoa']['label']
            wallet_map_key = wallet_data["wallet_type"].lower()
            
            # Construct the same key format used during creation
            address_map[f"{user_name_key}_{wallet_map_key}"] = address
            
            private_key = key_manager.get_private_key_hex(label)
            private_key_map[address] = private_key
            
    return address_map, private_key_map


async def create_and_map_users_and_wallets(
    node_context: NodeContext,
    user_profiles: List[Dict[str, Any]],
    passphrase_seed: Optional[str] = None
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Creates users and their wallets if they don't already exist, and returns
    comprehensive address and private key maps for all specified users.
    """
    if passphrase_seed is None:
        print("  ⚠️  Passphrase seed not provided. Defaulting to user's registered email for deterministic key generation.")
    else:
        print(f"  INFO: Using provided passphrase seed for key generation: {passphrase_seed[:8]}...")

    full_address_map = {}
    private_key_map = {}
    user_id_map = {}

    # 1. Create users if they don't exist.
    for profile in user_profiles:
        user_name = profile["name"]
        email_prefix = profile["email_prefix"]
        email = f"{email_prefix}@bachicoin.org"
        
        existing_user_id = node_context.user_service.storage.find_user_by_email(email)
        if existing_user_id:
            user_id_map[user_name] = existing_user_id
        else:
            print(f"--- Running User Setup for {user_name} ---")
            name_parts = user_name.split(" ", 1)
            profile_for_create = {
                "first_name": name_parts[0],
                "last_name": name_parts[1] if len(name_parts) > 1 else "",
                "email_registration": email,
                "user_type": profile.get("user_type", "individual")
            }
            user_id = create_user(node_context, profile_for_create)
            user_id_map[user_name] = user_id

    # 2. Create wallets for all specified users.
    for user_name, user_id in user_id_map.items():
        original_profile = next((p for p in user_profiles if p["name"] == user_name), None)
        user_type = original_profile.get("user_type", "individual") if original_profile else "individual"

        if user_type == "ledger":
            wallet_addresses = create_ledger_wallets(node_context, user_id)
        else:
            wallet_addresses = create_user_wallets(node_context, user_id, passphrase_seed=passphrase_seed)
        
        full_address_map.update(wallet_addresses)

    # 3. Build the private key map for all specified users.
    addr_map, p_key_map = get_maps_for_user_identities(node_context)
    
    # We only want to return the keys for the users we just processed
    newly_created_p_keys = {addr: key for addr, key in p_key_map.items() if addr in full_address_map.values()}

    return full_address_map, newly_created_p_keys


def bootstrap_register_validators(node_context: NodeContext, users_on_node: List[Dict[str, Any]], full_address_map: Dict[str, str]):
    """
    Registers users with 'validator' user_type as validators during the bootstrap process.
    This is a helper function for bootstrapping, not the core validator registration logic.
    """
    validator_service = node_context.validator_service
    wallet_service = node_context.wallet_service

    for user in users_on_node:
        if user['user_type'] == 'validator':
            user_name = user.get('name', f"{user['first_name']} {user['last_name']}")
            private_wallet_key = f"{user_name}_{'private'}" # Ensure consistent key format
            private_address = full_address_map.get(private_wallet_key)

            if not private_address:
                raise Exception(f"Could not find private wallet address for validator {user_name}")

            wallet_id = wallet_service.get_wallet_id_by_address(private_address)
            if not wallet_id:
                raise Exception(f"Could not find wallet ID for address {private_address}")

            validator_service.register_validator(user['user_id'], wallet_id)
            print(f"✅ Registered validator: {user_name} with private wallet {wallet_id[:12]}...")


if __name__ == "__main__":
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from tests.test_config import all_node_dirs
    from BachiCoin.lib_bootstrap.bootstrap_config import GENESIS_VALIDATORS


    async def main_smoke_test():
        """Smoke test for the create_and_map_users_and_wallets utility function."""
        print("=" * 70)
        print("🚀 Starting Smoke Test for bootstrap_utils.py")
        print("=" * 70)

        node_dirs = all_node_dirs[0]
        if node_dirs.base.exists():
            shutil.rmtree(node_dirs.base)
        node_dirs.ensure()

        node_context = NodeContext(
            user_service=UserServiceFactory.create_user_index_service(node_dirs),
            wallet_service=WalletServiceFactory.create_wallet_index_service(node_dirs),
            blockchain_service=BlockchainServiceFactory.create_blockchain_index_service(node_dirs),
            mempool_service=MempoolServiceFactory.create_mempool_index_service(node_dirs, broadcast_func=None),
            validator_service=ValidatorServiceFactory.create_validator_index_service(node_dirs),
            tx_service=TxServiceFactory.create_tx_index_service(node_dirs),
            proposer_service=ProposerServiceFactory.create_proposer_index_service(node_dirs),
            attestor_service=AttestorServiceFactory.create_attestor_index_service(node_dirs),
            finalizer_service=FinalizerServiceFactory.create_finalizer_index_service(node_dirs),
            node_dirs=node_dirs,
            port=0,
            network="testnet",
            currency="BACHI",
        )
        print("--- Minimal node context created for test ---")

        test_user_profiles = [
            {"name": "Ledger System", "email_prefix": "ledger.system", "user_type": "ledger"},
            {"name": "Gomer Adams", "email_prefix": "gomer.adams", "user_type": "individual"},
            *[{**p, "user_type": "validator"} for p in GENESIS_VALIDATORS],
        ]

        print("\n--- Calling create_and_map_users_and_wallets ---")
        address_map, p_key_map = await create_and_map_users_and_wallets(node_context, test_user_profiles)
        print("--- Utility function executed ---")

        print("\n--- Verifying results ---")
        assert node_context.user_service.search_users("Gomer Adams"), "Gomer Adams user was not created."
        print("✅ Users created successfully.")

        assert "Gomer Adams_private" in address_map
        print("✅ Address map contains expected wallets.")

        gomer_private_addr = address_map["Gomer Adams_private"]
        assert gomer_private_addr in p_key_map, "Private key for Gomer's private wallet is missing."
        print("✅ Private key map appears correct.")

        print("\n--- Testing get_maps_for_user_identities ---")
        full_addr_map, full_pkey_map = get_maps_for_user_identities(node_context)
        assert "Ledger System_mint" in full_addr_map
        assert "Staker A_private" in full_addr_map
        assert full_addr_map["Gomer Adams_private"] == gomer_private_addr
        assert len(full_pkey_map) >= len(p_key_map)
        print("✅ Identity scanning utility works as expected.")
        
        print("\n" + "=" * 70)
        print("🎉 Smoke Test for bootstrap_utils.py PASSED")
        print("=" * 70)

    asyncio.run(main_smoke_test())
