#!/usr/bin/env python3
"""
postprocess_state.py - A pure, stateless library for calculating state transitions.
It returns structured data and performs no direct console output.
This is the "Engine" of the post-processing module.
"""

import logging
from typing import Dict, Set, List, Any, TypedDict, Tuple
import json # Added for smoke test

from BachiCoin.lib_postprocess.postprocess_config import COMPUTATIONAL_DECIMAL_PLACES
from BachiCoin.lib_user.user_index_service import UserIndexService # Direct import
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService # Direct import
from BachiCoin.lib_transaction.tx_index_service import TxIndexService # Direct import
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService # Direct import

from BachiCoin.lib_nonce.nonce import increment_nonce
from BachiCoin.lib_transaction.tx_config import TxType
from BachiCoin.lib_crossmodule.node_context import NodeContext

# --- Data Structures for Clear API Contracts ---

class BalanceChange(TypedDict):
    """Details a single change to a wallet's balance."""
    wallet_id: str
    wallet_name: str
    change: float
    new_balance: float


class UpdateResult(TypedDict):
    """The structured result of processing a single block."""
    block_hash: str
    processed_tx_count: int
    skipped_tx_count: int
    affected_user_ids: Set[str]
    balance_changes: List[BalanceChange]
    errors: List[str]


# --- Internal Helper Functions ---

def _update_tx_records(
        all_node_contexts: Dict[int, NodeContext],
        block: Dict[str, Any]
) -> None:
    """
    Updates all transactions within a block to mark them as confirmed.
    This can be done on any node, as the tx database is replicated.
    """
    any_node_context = next(iter(all_node_contexts.values()))
    tx_service = any_node_context.tx_service
    transactions = block.get("transactions", [])
    block_hash = block.get("block_hash")
    block_height = block.get("height", -1)

    for tx in transactions:
        tx_service.update_transaction(tx.get("tx_hash"), update_data={
            "block_number": block_height,
            "block_hash": block_hash,
            "status": "confirmed"
        })


def _apply_block_balance_changes(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block: Dict[str, Any]
) -> Tuple[Set[str], List[BalanceChange], List[str], int]:
    """
    Calculates and applies all balance changes for transactions in a block.
    Crucially, it uses the correct node context for each address.
    """
    transactions = block.get("transactions", [])
    users_to_reconcile: Dict[str, NodeContext] = {}  # Maps user_id to their home node context
    balance_changes: List[BalanceChange] = []
    errors: List[str] = []
    sender_tx_counts: Dict[str, int] = {}
    processed_count = 0
    
    any_tx_service = next(iter(all_node_contexts.values())).tx_service

    def _get_context_for_address(addr: str) -> Tuple[NodeContext, str]:
        """Helper to get the right context and wallet ID for an address."""
        node_id = address_to_node_map.get(addr)
        if node_id is None:
            raise ValueError(f"Address {addr} not found in the provided address-to-node map.")
        
        node_context = all_node_contexts.get(node_id)
        if node_context is None:
            raise ValueError(f"Node context for node ID {node_id} not found.")

        wallet_id = node_context.wallet_service.get_wallet_id_by_address(addr)
        if wallet_id is None:
            raise ValueError(f"Wallet ID for address {addr} not found on its home node {node_id}.")
            
        return node_context, wallet_id

    # Helper to get system wallets, assuming they are on Node 0
    node_0_context = all_node_contexts[0]
    all_users_list = node_0_context.user_service.list_users()
    ledger_system_user = next((u for u in all_users_list if f"{u.get('first_name')} {u.get('last_name')}" == "Ledger System"), None)
    
    burn_wallet_id = None
    pool_wallet_id = None
    if ledger_system_user:
        ledger_system_wallets = node_0_context.wallet_service.list_wallets_by_user(ledger_system_user['user_id'])
        burn_wallet = next((w for w in ledger_system_wallets if w['wallet_type'] == 'burn'), None)
        pool_wallet = next((w for w in ledger_system_wallets if w['wallet_type'] == 'pool'), None)
        if burn_wallet:
            burn_wallet_id = burn_wallet['wallet_id']
        if pool_wallet:
            pool_wallet_id = pool_wallet['wallet_id']


    for tx in transactions:
        # THE CRITICAL CHECK: Has this transaction already been applied?
        existing_tx = any_tx_service.get_transaction(tx['tx_hash'])
        if existing_tx and existing_tx.get('status') == 'confirmed':
            logging.warning(f"Transaction {tx['tx_hash'][:10]} has already been confirmed. Skipping state update.")
            continue

        tx_type = tx.get("tx_type")
        from_addr = tx.get("from_address")
        to_addr = tx.get("to_address")
        amount = round(tx.get("amount", 0.0), COMPUTATIONAL_DECIMAL_PLACES)
        gas_fee = round(tx.get("total_fee", 0.0), COMPUTATIONAL_DECIMAL_PLACES)

        processed_count += 1

        if tx_type == TxType.MINT.value:
            to_node_context, to_wallet_id = _get_context_for_address(to_addr)
            wallet_data = to_node_context.wallet_service.get_wallet(to_wallet_id)
            new_balance = wallet_data.get("balance", 0.0) + amount
            to_node_context.wallet_service.update_account_state(to_wallet_id, balance=new_balance)
            users_to_reconcile[wallet_data["user_id"]] = to_node_context
            balance_changes.append({"wallet_id": to_wallet_id, "wallet_name": wallet_data["name"], "change": amount, "new_balance": new_balance})

        elif tx_type == TxType.REWARD.value:
            # Credit user
            to_node_context, to_wallet_id = _get_context_for_address(to_addr)
            wallet_data = to_node_context.wallet_service.get_wallet(to_wallet_id)
            new_balance = wallet_data.get("balance", 0.0) + amount
            to_node_context.wallet_service.update_account_state(to_wallet_id, balance=new_balance)
            users_to_reconcile[wallet_data["user_id"]] = to_node_context
            balance_changes.append({"wallet_id": to_wallet_id, "wallet_name": wallet_data["name"], "change": amount, "new_balance": new_balance})
            # Debit pool
            if pool_wallet_id:
                pool_wallet_data = node_0_context.wallet_service.get_wallet(pool_wallet_id)
                new_pool_balance = pool_wallet_data.get("balance", 0.0) - amount
                node_0_context.wallet_service.update_account_state(pool_wallet_id, balance=new_pool_balance)
                users_to_reconcile[pool_wallet_data["user_id"]] = node_0_context
                balance_changes.append({"wallet_id": pool_wallet_id, "wallet_name": pool_wallet_data["name"], "change": -amount, "new_balance": new_pool_balance})

        elif tx_type == TxType.TRANSFER.value:
            # Debit sender
            from_node_context, from_wallet_id = _get_context_for_address(from_addr)
            from_wallet_data = from_node_context.wallet_service.get_wallet(from_wallet_id)
            new_from_balance = from_wallet_data.get("balance", 0.0) - (amount + gas_fee)
            from_node_context.wallet_service.update_account_state(from_wallet_id, balance=new_from_balance)
            sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
            users_to_reconcile[from_wallet_data["user_id"]] = from_node_context
            balance_changes.append({"wallet_id": from_wallet_id, "wallet_name": from_wallet_data["name"], "change": -(amount + gas_fee), "new_balance": new_from_balance})
            # Credit receiver
            to_node_context, to_wallet_id = _get_context_for_address(to_addr)
            to_wallet_data = to_node_context.wallet_service.get_wallet(to_wallet_id)
            new_to_balance = to_wallet_data.get("balance", 0.0) + amount
            to_node_context.wallet_service.update_account_state(to_wallet_id, balance=new_to_balance)
            users_to_reconcile[to_wallet_data["user_id"]] = to_node_context
            balance_changes.append({"wallet_id": to_wallet_id, "wallet_name": to_wallet_data["name"], "change": amount, "new_balance": new_to_balance})

        elif tx_type == TxType.BURN.value:
            # Debit user
            from_node_context, from_wallet_id = _get_context_for_address(from_addr)
            from_wallet_data = from_node_context.wallet_service.get_wallet(from_wallet_id)
            new_from_balance = from_wallet_data.get("balance", 0.0) - (amount + gas_fee)
            from_node_context.wallet_service.update_account_state(from_wallet_id, balance=new_from_balance)
            sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
            users_to_reconcile[from_wallet_data["user_id"]] = from_node_context
            balance_changes.append({"wallet_id": from_wallet_id, "wallet_name": from_wallet_data["name"], "change": -(amount + gas_fee), "new_balance": new_from_balance})
            # Credit burn wallet
            if burn_wallet_id:
                burn_wallet_data = node_0_context.wallet_service.get_wallet(burn_wallet_id)
                new_burn_balance = burn_wallet_data.get("balance", 0.0) + amount
                node_0_context.wallet_service.update_account_state(burn_wallet_id, balance=new_burn_balance)
                users_to_reconcile[burn_wallet_data["user_id"]] = node_0_context
                balance_changes.append({"wallet_id": burn_wallet_id, "wallet_name": burn_wallet_data["name"], "change": amount, "new_balance": new_burn_balance})

        elif tx_type == TxType.SLASH.value:
            # Debit user
            from_node_context, from_wallet_id = _get_context_for_address(from_addr)
            from_wallet_data = from_node_context.wallet_service.get_wallet(from_wallet_id)
            new_from_balance = from_wallet_data.get("balance", 0.0) - (amount + gas_fee)
            from_node_context.wallet_service.update_account_state(from_wallet_id, balance=new_from_balance)
            sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
            users_to_reconcile[from_wallet_data["user_id"]] = from_node_context
            balance_changes.append({"wallet_id": from_wallet_id, "wallet_name": from_wallet_data["name"], "change": -(amount + gas_fee), "new_balance": new_from_balance})
            # Credit pool
            if pool_wallet_id:
                pool_wallet_data = node_0_context.wallet_service.get_wallet(pool_wallet_id)
                new_pool_balance = pool_wallet_data.get("balance", 0.0) + amount
                node_0_context.wallet_service.update_account_state(pool_wallet_id, balance=new_pool_balance)
                users_to_reconcile[pool_wallet_data["user_id"]] = node_0_context
                balance_changes.append({"wallet_id": pool_wallet_id, "wallet_name": pool_wallet_data["name"], "change": amount, "new_balance": new_pool_balance})

        elif tx_type == TxType.STAKE.value:
            # Debit user
            from_node_context, from_wallet_id = _get_context_for_address(from_addr)
            from_wallet_data = from_node_context.wallet_service.get_wallet(from_wallet_id)
            new_from_balance = from_wallet_data.get("balance", 0.0) - (amount + gas_fee)
            from_node_context.wallet_service.update_account_state(from_wallet_id, balance=new_from_balance)
            sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
            users_to_reconcile[from_wallet_data["user_id"]] = from_node_context
            balance_changes.append({"wallet_id": from_wallet_id, "wallet_name": from_wallet_data["name"], "change": -(amount + gas_fee), "new_balance": new_from_balance})
            # Credit pool
            if pool_wallet_id:
                pool_wallet_data = node_0_context.wallet_service.get_wallet(pool_wallet_id)
                new_pool_balance = pool_wallet_data.get("balance", 0.0) + amount
                node_0_context.wallet_service.update_account_state(pool_wallet_id, balance=new_pool_balance)
                users_to_reconcile[pool_wallet_data["user_id"]] = node_0_context
                balance_changes.append({"wallet_id": pool_wallet_id, "wallet_name": pool_wallet_data["name"], "change": amount, "new_balance": new_pool_balance})

        elif tx_type == TxType.UNSTAKE.value:
            # Debit pool
            from_node_context, from_wallet_id = _get_context_for_address(from_addr)
            from_wallet_data = from_node_context.wallet_service.get_wallet(from_wallet_id)
            new_from_balance = from_wallet_data.get("balance", 0.0) - amount
            from_node_context.wallet_service.update_account_state(from_wallet_id, balance=new_from_balance)
            sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
            users_to_reconcile[from_wallet_data["user_id"]] = from_node_context
            balance_changes.append({"wallet_id": from_wallet_id, "wallet_name": from_wallet_data["name"], "change": -amount, "new_balance": new_from_balance})
            # Credit user
            to_node_context, to_wallet_id = _get_context_for_address(to_addr)
            to_wallet_data = to_node_context.wallet_service.get_wallet(to_wallet_id)
            new_to_balance = to_wallet_data.get("balance", 0.0) + amount
            to_node_context.wallet_service.update_account_state(to_wallet_id, balance=new_to_balance)
            users_to_reconcile[to_wallet_data["user_id"]] = to_node_context
            balance_changes.append({"wallet_id": to_wallet_id, "wallet_name": to_wallet_data["name"], "change": amount, "new_balance": new_to_balance})

        else:
            processed_count -= 1
            errors.append(f"Tx {tx['tx_hash'][:10]}: Unknown tx_type '{tx_type}'.")

    for addr, count in sender_tx_counts.items():
        node_context, _ = _get_context_for_address(addr)
        increment_nonce(addr, node_context.wallet_service, count)

    for user_id, node_context in users_to_reconcile.items():
        node_context.wallet_service.reconcile_user_balance(user_id)

    return set(users_to_reconcile.keys()), balance_changes, errors, processed_count


# --- Core Public Function ---

def update_block_state(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block_hash: str
) -> UpdateResult:
    """
    Processes a block, updates transaction records, and calculates all state changes
    using a decentralized approach.
    """
    any_node_context = next(iter(all_node_contexts.values()))
    block = any_node_context.blockchain_service.get_block(block_hash)

    if not block:
        return {
            "block_hash": block_hash, "processed_tx_count": 0, "skipped_tx_count": 0,
            "affected_user_ids": set(), "balance_changes": [], "errors": ["Block not found."]
        }

    if block.get("state_processed"):
        logging.warning(f"Block {block_hash[:10]} has already been processed. Skipping.")
        return {
            "block_hash": block_hash, "processed_tx_count": 0, "skipped_tx_count": len(block.get("transactions", [])),
            "affected_user_ids": set(), "balance_changes": [], "errors": [f"Block {block_hash[:10]} already processed."]
        }

    affected_users, balance_changes, errors, processed_count = _apply_block_balance_changes(
        all_node_contexts, address_to_node_map, block
    )
    
    # Only update transaction records after the balance changes are successfully applied
    _update_tx_records(all_node_contexts, block)
    
    any_node_context.blockchain_service.update_block(block_hash, {"state_processed": True})
    logging.info(f"Successfully processed and marked block {block_hash[:10]} as state_processed=True.")


    total_tx_in_block = len(block.get("transactions", []))
    skipped_count = total_tx_in_block - processed_count

    return {
        "block_hash": block_hash,
        "processed_tx_count": processed_count,
        "skipped_tx_count": skipped_count,
        "affected_user_ids": affected_users,
        "balance_changes": balance_changes,
        "errors": errors
    }


# --- Granular "Getter" Functions ---

def get_ledger_balance(all_node_contexts: Dict[int, NodeContext]) -> float:
    """Calculates the total sum of all balances across all wallets on all nodes."""
    total = 0.0
    for node_context in all_node_contexts.values():
        total += sum(
            w.get("balance", 0.0) for w in node_context.wallet_service.list_wallets()
        )
    return round(total, COMPUTATIONAL_DECIMAL_PLACES)


def get_ledger_summary(all_node_contexts: Dict[int, NodeContext]) -> Dict[str, Any]:
    """Returns high-level aggregate data for the entire ledger across all nodes."""
    total_wallets = 0
    total_users = 0
    for node_context in all_node_contexts.values():
        total_wallets += len(node_context.wallet_service.list_wallets())
        total_users += len(node_context.user_service.list_users())

    return {
        "total_balance": get_ledger_balance(all_node_contexts),
        "wallet_count": total_wallets,
        "user_count": total_users
    }


def get_user_balance(node_context: NodeContext, user_id: str) -> Dict[str, Any]:
    """Returns the total balance for a single user on a specific node."""
    wallet_service = node_context.wallet_service
    user_wallets = [w for w in wallet_service.list_wallets() if w.get("user_id") == user_id]
    balance = sum(w.get("balance", 0.0) for w in user_wallets)
    user_data = node_context.user_service.get_user(user_id)
    return {
        "user_id": user_id,
        "name": f"{user_data.get('first_name')} {user_data.get('last_name')}",
        "total_balance": round(balance, COMPUTATIONAL_DECIMAL_PLACES),
        "wallet_count": len(user_wallets)
    }


def get_wallet_balance(node_context: NodeContext, wallet_id: str) -> Dict[str, Any]:
    """Returns detailed balance information for a single wallet on a specific node."""
    w_data = node_context.wallet_service.get_wallet(wallet_id)
    return {
        "wallet_id": wallet_id,
        "name": w_data.get("name"),
        "balance": round(w_data.get("balance", 0.0), COMPUTATIONAL_DECIMAL_PLACES),
        "nonce": w_data.get("nonce", 0)
    }


# --- Service Management ---

def close_services(all_node_contexts: Dict[int, NodeContext]) -> None:
    """Closes all service connections within all provided NodeContexts."""
    for node_context in all_node_contexts.values():
        for attr_name in dir(node_context):
            if attr_name.endswith("_service"):
                service = getattr(node_context, attr_name)
                if service and hasattr(service, "close"):
                    try:
                        service.close()
                    except Exception as e:
                        print(f"Warning closing service {attr_name} on node: {e}")


# --- Smoke Test ---
if __name__ == '__main__':
    from tests.test_config import dirs
    import json

    # Import service factories
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory # Direct import
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory # Direct import
    from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory # Direct import
    from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory # Direct import

    print("\n🔹 Initializing services for smoke test...")
    
    # Create services using factories
    user_service = UserServiceFactory.create_user_index_service(dirs)
    wallet_service = WalletServiceFactory.create_wallet_index_service(dirs, user_service=user_service)
    blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(dirs)
    tx_service = TxServiceFactory.create_tx_index_service(dirs, wallet_index_service=wallet_service)

    test_node_context = NodeContext(
        node_dirs=dirs,
        user_service=user_service,
        wallet_service=wallet_service,
        blockchain_service=blockchain_service,
        tx_service=tx_service
    )
    
    mock_all_node_contexts = {0: test_node_context}
    
    mock_address_to_node_map = {}
    wallet_summaries = test_node_context.wallet_service.list_wallets()
    for summary in wallet_summaries:
        wallet_id = summary.get("wallet_id")
        if wallet_id:
            wallet_data = test_node_context.wallet_service.get_wallet(wallet_id)
            if wallet_data and wallet_data.get("address"):
                mock_address_to_node_map[wallet_data["address"]] = 0

    blocks_with_txs = [b for b in test_node_context.blockchain_service.list_blocks() if b.get("transaction_count", 0) > 0]

    if not blocks_with_txs:
        print("\n❌ Smoke Test Failed: No blocks with transactions found to process.")
    else:
        test_block = blocks_with_txs[0]
        block_hash = test_block['block_hash']
        print(f"\n⚙️  Testing with block {block_hash[:16]}...")

        try:
            result = update_block_state(mock_all_node_contexts, mock_address_to_node_map, block_hash)

            print("\n--- 1. RAW UpdateResult OBJECT ---")
            result_display = result.copy()
            result_display["affected_user_ids"] = list(result.get("affected_user_ids", []))
            print(json.dumps(result_display, indent=2))

            print("\n--- 2. SIMULATED ORCHESTRATOR REPORT ---")
            if result["errors"]:
                print(f"❌ Errors found: {result['errors']}")
            
            print(f"✅ Processed {result['processed_tx_count']} of {test_block.get('transaction_count', 0)} transactions.")
            if result['skipped_tx_count'] > 0:
                print(f"⚠️  Skipped {result['skipped_tx_count']} transactions.")

            if result["affected_user_ids"]:
                print("\n--- Balance Updates ---")
                for user_id in sorted(list(result["affected_user_ids"])):
                    user_summary = get_user_balance(test_node_context, user_id)
                    print(f"  👤 User '{user_summary['name']}' new total balance: {user_summary['total_balance']:.2f} BACHI")
            
            print("\n--- 3. FINAL LEDGER STATE ---")
            final_summary = get_ledger_summary(mock_all_node_contexts)
            print(f"✅ System Final State: {final_summary['total_balance']:.2f} BACHI across {final_summary['wallet_count']} wallets.")
            
            print(f"   (Raw Ledger Balance for Conservation Check: {get_ledger_balance(mock_all_node_contexts)})")

        except ValueError as e:
            print(f"\n💥 SMOKE TEST FAILED AS EXPECTED: {e}")


    print("\n🔹 Closing services...")
    close_services(mock_all_node_contexts)
    print("\n🎯 Done.")
