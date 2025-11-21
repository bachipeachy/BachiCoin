#!/usr/bin/env python3
"""bootstrap_ledger.py - Handles the initial creation of the BachiCoin ledger."""

import asyncio

from BachiCoin.lib_bootstrap.bootstrap_config import GENESIS_MINT_AMOUNT
from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_mempool.mempool_service_factory import MempoolServiceFactory
from BachiCoin.lib_transaction.tx_config import TxConfig
from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
from BachiCoin.lib_transaction.tx_submittal import create_signed_tx
# Direct imports for service factories
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory


async def bootstrap_ledger(
        node_context: NodeContext,
) -> str:
    """Bootstraps the ledger by creating and submitting the genesis mint transaction."""
    print("---" * 10)
    print("--- Bootstrapping Ledger: Submitting Genesis Mint Transaction ---")
    print("---" * 10)
    mempool_service = node_context.mempool_service

    # 1. Define the transaction template for the genesis mint.
    mint_tx_template = {
        "tx_type": "mint",
        "amount": GENESIS_MINT_AMOUNT,  # Use constant from config
        "to_ref": {"user": "Ledger System", "wallet": "mint"},
        "memo": "System Genesis Mint Transaction",
        "priority": "urgent",
        "tx_version": TxConfig.DEFAULT_TX_VERSION,  # Added for canonical hashing
    }

    # 2. Use the generic 'create_signed_tx' function.
    system_tx = create_signed_tx(
        node_context=node_context,
        tx_template=mint_tx_template,
        global_address_book=node_context.address_map,  # Use node_context.address_map
        nonce=None  # Not needed for system tx
    )

    tx_hash = system_tx.get("tx_hash")
    if not tx_hash:
        raise Exception("Failed to create genesis mint transaction.")

    # 3. Submit the system transaction to the mempool.
    await mempool_service.submit_tx(system_tx)
    print(f"  ✅ Genesis Mint Tx {tx_hash[:12]}... submitted to mempool.")

    return tx_hash


if __name__ == "__main__":
    import shutil
    from pathlib import Path
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from tests.test_config import all_node_dirs
    from BachiCoin.lib_bootstrap.bootstrap_utils import create_and_map_users_and_wallets
    from BachiCoin.lib_crossmodule.crossmodule_config import NetworkType, Currency


    async def main_smoke_test():
        """Smoke test for the bootstrap_ledger function."""
        print("=" * 70)
        print("🚀 Starting Smoke Test for bootstrap_ledger.py")
        print("=" * 70)

        # 1. Use the standard test directory for Node 0 and DO NOT clean it.
        node_dirs = all_node_dirs[0]
        if node_dirs.base.exists():
            shutil.rmtree(node_dirs.base)
        node_dirs.ensure()

        # 2. Create a minimal node context with the required services
        node_context = NodeContext(
            user_service=UserServiceFactory.create_user_index_service(node_dirs),
            wallet_service=WalletServiceFactory.create_wallet_index_service(node_dirs),
            validator_service=ValidatorServiceFactory.create_validator_index_service(node_dirs),
            mempool_service=MempoolServiceFactory.create_mempool_index_service(node_dirs),
            tx_service=TxServiceFactory.create_tx_index_service(node_dirs),
            node_dirs=node_dirs,
            port=0,
            network=NetworkType.TESTNET.value,
            currency=Currency.BACHI.value
        )
        print("--- Minimal node context created for test ---")

        # 3. SETUP: Create Ledger System and Genesis User using bootstrap_utils
        print("\n--- Setting up Ledger System and Genesis User ---")
        bootstrap_user_profiles = [
            {"name": "Ledger System", "email_prefix": "ledger.system", "user_type": "ledger"},
            {"name": "Genesis User", "email_prefix": "genesis.user", "user_type": "genesis"},
        ]
        address_map, private_key_map = await create_and_map_users_and_wallets(node_context, bootstrap_user_profiles)

        # Populate node_context with the created maps
        node_context.address_map = address_map
        setattr(node_context, 'private_key_map', private_key_map)
        print("--- Ledger System and Genesis User setup complete ---\n")

        # 4. EXECUTION: Call the function under test
        tx_hash = await bootstrap_ledger(node_context)  # No address_map parameter

        # 5. VERIFICATION
        print("\n--- Verifying ledger bootstrap ---")
        assert tx_hash is not None and len(tx_hash) > 0
        print("✅ Function returned a transaction hash.")

        pending_txs = node_context.mempool_service.get_pending_transactions()
        assert len(pending_txs) == 1, f"Expected 1 transaction in mempool, but found {len(pending_txs)}"
        print("✅ Correct number of transactions found in mempool.")

        assert pending_txs[0]['tx_hash'] == tx_hash
        print("✅ Mempool transaction hash matches returned hash.")

        # Verify tx_version is present in the submitted transaction
        submitted_tx = node_context.tx_service.get_transaction(tx_hash)
        assert submitted_tx is not None
        assert submitted_tx.get("tx_version") == TxConfig.DEFAULT_TX_VERSION
        print("✅ Submitted transaction contains correct tx_version.")

        print("\nNOTE: Test data remains in the standard test directory for inspection.")
        print("=" * 70)
        print("🎉 Smoke Test for bootstrap_ledger PASSED")
        print("=" * 70)


    asyncio.run(main_smoke_test())
