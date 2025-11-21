#!/usr/bin/env python3
"""tx_submittal.py - create, sign and submit transaction(s) for user as well as system tx's"""

import random
import asyncio
from typing import Dict, Any, Optional, Set

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_transaction.tx_signer import create_canonical_tx_hash
from BachiCoin.lib_transaction.tx_config import TxConfig, TxType
from BachiCoin.lib_nonce.nonce import calculate_next_nonce
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils

# Define transaction types based on their signature and nonce requirements
USER_SIGNED_TX_TYPES: Set[str] = {TxType.TRANSFER.value, TxType.STAKE.value, TxType.UNSTAKE.value, TxType.BURN.value}
SYSTEM_TX_TYPES: Set[str] = {TxType.MINT.value, TxType.SLASH.value, TxType.REWARD.value}

def get_pvt_key_for_address(address: str, pvt_key_map: Dict[str, str]) -> Optional[str]:
    """JIT helper to retrieve a private key from an in-memory map."""
    return pvt_key_map.get(address)

def create_signed_tx(
        node_context: NodeContext,
        tx_template: Dict[str, Any],
        global_address_book: Dict[str, str],
        pvt_key_map: Optional[Dict[str, str]] = None,
        nonce: Optional[int] = None
) -> Dict[str, Any]:
    """
    Creates and, if necessary, signs a transaction based on its type, handling special
    addressing rules for system transactions.
    """
    tx_service = node_context.tx_service
    tx_type = tx_template.get("tx_type")
    if not tx_type:
        raise ValueError("Transaction template must include a 'tx_type'.")

    from_ref = tx_template.get("from_ref")
    to_ref = tx_template.get("to_ref")

    # 1. Resolve from_address based on from_ref
    from_address = None
    if from_ref:
        from_user_key = f"{from_ref['user']}_{from_ref['wallet']}"
        from_address = global_address_book.get(from_user_key)
        if not from_address:
            raise ValueError(f"Could not resolve from_address for key: {from_user_key}")

    # 2. Resolve to_address with special handling for tx_type
    to_address = None
    if tx_type == TxType.STAKE.value:
        to_address = global_address_book.get("Ledger System_pool")
        if not to_address:
            raise ValueError("Staking pool address 'Ledger System_pool' not found in address book.")
    elif tx_type == TxType.UNSTAKE.value:
        # For unstake, the recipient is the sender unless otherwise specified.
        if to_ref:
             to_user_key = f"{to_ref['user']}_{to_ref['wallet']}"
             to_address = global_address_book.get(to_user_key)
        else:
             to_address = from_address
    elif to_ref:
        to_user_key = f"{to_ref['user']}_{to_ref['wallet']}"
        to_address = global_address_book.get(to_user_key)
        if not to_address:
            raise ValueError(f"Could not resolve to_address for key: {to_user_key}")

    # 3. Determine if nonce and signature are required based on transaction type
    is_user_signed = tx_type in USER_SIGNED_TX_TYPES
    
    if is_user_signed and nonce is None:
        raise ValueError(f"Nonce must be provided for user-signed transaction type: '{tx_type}'.")
    if not is_user_signed and nonce is not None:
        raise ValueError(f"Nonce must not be provided for system transaction type: '{tx_type}'.")

    # 4. Create the transaction payload
    tx_payload = {
        "amount": tx_template["amount"],
        "tx_type": tx_type,
        "memo": tx_template.get("memo", f"TX Type: {tx_type}"),
        "tx_version": tx_template.get("tx_version", TxConfig.DEFAULT_TX_VERSION),
        **TxConfig.FEE_DEFAULTS.get(tx_template.get("priority", "standard"), TxConfig.FEE_DEFAULTS["standard"])
    }

    unsigned_tx = tx_service.create_tx_with_index(
        from_address=from_address,
        to_address=to_address,
        tx_data=tx_payload,
        calculated_nonce=nonce
    )

    # 5. Sign the transaction if required
    tx_hash = create_canonical_tx_hash(unsigned_tx)
    final_tx = unsigned_tx.copy()
    final_tx['tx_hash'] = tx_hash

    if is_user_signed:
        if pvt_key_map is None:
            raise ValueError("pvt_key_map must be provided for user-signed transactions.")
        
        private_key = get_pvt_key_for_address(from_address, pvt_key_map)
        if not private_key:
            raise ValueError(f"Private key for address '{from_address}' not found for signing!")

        signature = "0x" + CryptoUtils.sign_message_recoverable(bytes.fromhex(tx_hash[2:]), private_key)
        final_tx['signature'] = signature
    else:
        final_tx.pop('signature', None)

    # 6. Save the final transaction
    tx_service.save_signed_transaction(final_tx)
    return final_tx


async def submit_txs_for_user(
        node_context: NodeContext,
        user_name: str,
        user_tx_templates: list,
        global_address_book: Dict[str, str],
        pvt_key_map: Dict[str, str]
) -> int:
    """Submits all transactions for a specific user, handling both user-signed and system tx."""
    if not user_tx_templates:
        return 0

    wallet_service = node_context.wallet_service
    mempool_service = node_context.mempool_service

    nonce_map = {}
    for tx in user_tx_templates:
        if tx.get("tx_type") in USER_SIGNED_TX_TYPES and tx.get("from_ref"):
            key = f"{tx['from_ref']['user']}_{tx['from_ref']['wallet']}"
            addr = global_address_book.get(key)
            if addr and addr not in nonce_map:
                pending_txs = mempool_service.get_pending_transactions()
                nonce_map[addr] = calculate_next_nonce(addr, wallet_service, pending_txs)

    num_submitted = 0
    for tx_template in user_tx_templates:
        tx_type = tx_template.get("tx_type")
        from_ref = tx_template.get("from_ref")
        
        current_nonce = None
        if tx_type in USER_SIGNED_TX_TYPES and from_ref:
            from_user_key = f"{from_ref['user']}_{from_ref['wallet']}"
            from_address = global_address_book.get(from_user_key)
            if not from_address: continue

            current_nonce = nonce_map[from_address]
            nonce_map[from_address] += 1

        signed_tx = create_signed_tx(
            node_context, tx_template, global_address_book, pvt_key_map, current_nonce
        )

        await asyncio.sleep(random.uniform(0.05, 0.2))
        await mempool_service.submit_tx(signed_tx)
        num_submitted += 1

    return num_submitted


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
    from tests.test_config import all_node_dirs
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory

    # Mock NodeContext and BlockchainService for isolated testing
    class MockBlockchainService:
        def get_nonce_and_balance(self, address: str) -> Dict[str, Any]:
            # Simulate some account states for testing
            if address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":
                return {"nonce": 5, "balance": 100.0}
            elif address == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb":
                return {"nonce": 10, "balance": 200.0}
            return {"nonce": 0, "balance": 0.0}

    class MockMempoolService: # This mock is for mempool_lib_api.get_pending_transactions
        def get_pending_transactions(self): return []

    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                user_service=UserServiceFactory.create_user_index_service(dirs),
                wallet_service=WalletServiceFactory.create_wallet_index_service(dirs),
                blockchain_service=MockBlockchainService(), # Use mock blockchain service
                mempool_service=MockMempoolService(), # Use mock mempool service
                validator_service=None, # Not needed for this mock
                tx_service=TxServiceFactory.create_tx_index_service(dirs), # Real tx_service
                proposer_service=None, # Not needed for this mock
                attestor_service=None, # Not needed for this mock
                finalizer_service=None, # Not needed for this mock
                node_dirs=dirs,
                port=0, network="testnet", currency="BACHI"
            )
    
    mock_node_context = MockNodeContext(all_node_dirs[0])

    mock_address_book = {
        "Gomer_private": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        "Isha_business": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
        "Ledger System_pool": "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
    }
    mock_pvt_key_map = {
        "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d734123f129"
    }

    def run_test(test_name, template, nonce, should_pass=True):
        print(f"\n--- Running: {test_name} ---")
        try:
            tx = create_signed_tx(mock_node_context, template, mock_address_book, mock_pvt_key_map, nonce)
            print(f"  ✅ SUCCESS: Created tx_hash: {tx['tx_hash'][:12]}...")
            if not should_pass:
                print(f"  ❌ FAIL: Test was expected to fail but succeeded.")
                return False
            # Additional check for unstake
            if template['tx_type'] == 'unstake':
                assert tx['to_address'] == tx['from_address'], "to_address should equal from_address for unstake"
                print("  ✅ VERIFIED: Unstake 'to_address' is correct.")
            return True
        except Exception as e:
            if should_pass:
                print(f"  ❌ FAIL: {e}")
                return False
            else:
                print(f"  ✅ SUCCESS: Test failed as expected: {e}")
                return True

    tests = [
        ("Valid TRANSFER", {"tx_type": "transfer", "amount": 1.0, "from_ref": {"user": "Gomer", "wallet": "private"}, "to_ref": {"user": "Isha", "wallet": "business"}}, 0, True),
        ("Valid STAKE", {"tx_type": "stake", "amount": 100.0, "from_ref": {"user": "Gomer", "wallet": "private"}}, 1, True),
        ("Valid UNSTAKE (no to_ref)", {"tx_type": "unstake", "amount": 50.0, "from_ref": {"user": "Gomer", "wallet": "private"}}, 2, True),
        ("Valid BURN", {"tx_type": "burn", "amount": 5.0, "from_ref": {"user": "Gomer", "wallet": "private"}}, 3, True),
        ("Valid MINT", {"tx_type": "mint", "amount": 1000.0, "to_ref": {"user": "Isha", "wallet": "business"}}, None, True),
        ("Valid REWARD", {"tx_type": "reward", "amount": 10.0, "to_ref": {"user": "Gomer", "wallet": "private"}}, None, True),
        ("Valid SLASH", {"tx_type": "slash", "amount": 20.0, "from_ref": {"user": "Gomer", "wallet": "private"}}, None, True),
        ("Invalid TRANSFER (missing nonce)", {"tx_type": "transfer", "amount": 1.0, "from_ref": {"user": "Gomer", "wallet": "private"}, "to_ref": {"user": "Isha", "wallet": "business"}}, None, False),
        ("Invalid MINT (with nonce)", {"tx_type": "mint", "amount": 1000.0, "to_ref": {"user": "Isha", "wallet": "business"}}, 0, False),
    ]
    
    results = []
    for name, template, nonce, should_pass in tests:
        results.append(run_test(name, template, nonce, should_pass))

    pool_addr_key = "Ledger System_pool"
    original_pool_addr = mock_address_book.pop(pool_addr_key)
    results.append(run_test(
        "Invalid STAKE (missing pool address)",
        {"tx_type": "stake", "amount": 100.0, "from_ref": {"user": "Gomer", "wallet": "private"}},
        4,
        False
    ))
    mock_address_book[pool_addr_key] = original_pool_addr

    print("\n--- SMOKE TEST SUMMARY ---")
    if all(results):
        print("🎉 ALL TESTS PASSED")
    else:
        print("🔥 SOME TESTS FAILED")
        sys.exit(1)
