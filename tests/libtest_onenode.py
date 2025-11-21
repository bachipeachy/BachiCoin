"""Orchestrator for end-to-end loopback testing."""
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set

from BachiCoin.api_public import (
    user_lib_api,
    wallet_lib_api,
    blockchain_lib_api,
    postprocess_lib_api,
    bootstrap_lib_api,
    tx_lib_api,
    consensus_lib_api,
    crossmodule_lib_api,
)
from tests.test_config import dirs
from tests.libtest_data import REGULAR_USERS, TRANSACTION_SCHEDULE

# --- Test Configuration ---
TARGET_SLOTS = 64

# --- Global variable to hold the "before" state for comparison ---
before_state_summary: Dict[str, Any] = {}


def get_address_book_path(node_dir: Path) -> Path:
    """Returns the standardized path for the global address book."""
    return node_dir / "public" / "global_address_book.json"


async def check_for_background_exceptions():
    """Helper to check for exceptions in other tasks and propagate them."""
    await asyncio.sleep(0.1)
    for task in asyncio.all_tasks():
        if task is not asyncio.current_task() and task.done() and not task.cancelled():
            exception = task.exception()
            if exception:
                print(f"\n--- 💥 BACKGROUND TASK FAILED! ---")
                raise exception


def display_per_node_summary(node_context: crossmodule_lib_api.NodeContext):
    """Displays a detailed state summary for the single node."""
    print("\n" + "="*80)
    print("--- NODE STATE SUMMARY ---")
    print("="*80)
    
    print(f"\n--- Node State ---")
    
    local_users = user_lib_api.list_users(node_context.user_service)
    local_wallets = wallet_lib_api.list_wallets(node_context.wallet_service)
    
    local_total_balance = sum(w.get('balance', 0.0) for w in local_wallets)
    
    print(f"  👥 Local Users: {len(local_users)}")
    for user in local_users:
        user_balance = sum(w.get('balance', 0.0) for w in local_wallets if w.get('user_id') == user['user_id'])
        print(f"    - {user.get('first_name')} {user.get('last_name')}: {user_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")
        
    print(f"  💰 Local Ledger Balance: {local_total_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI in {len(local_wallets)} wallets.")
        
    print("\n" + "="*80)


def capture_or_display_summary(
        node_context: crossmodule_lib_api.NodeContext,
        header: str,
        is_final_summary: bool = False
):
    """Captures the initial system state or displays a before-and-after comparison for the single node."""
    global before_state_summary

    all_users = []
    all_user_ids = set()
    for user in user_lib_api.list_users(node_context.user_service):
        if user['user_id'] not in all_user_ids:
            all_users.append(user)
            all_user_ids.add(user['user_id'])

    current_user_balances = {}
    for user in all_users:
        user_id = user['user_id']
        total_balance = 0.0
        user_wallets = wallet_lib_api.list_wallets_by_user(node_context.wallet_service, user_id)
        for wallet in user_wallets:
            total_balance += wallet.get('balance', 0.0)
        
        current_user_balances[user_id] = {
            "user_id": user_id,
            "name": f"{user.get('first_name')} {user.get('last_name')}",
            "total_balance": total_balance
        }

    # Add system wallets (pool and burn)
    all_users_list = user_lib_api.list_users(node_context.user_service)
    ledger_system_user = next((u for u in all_users_list if f"{u.get('first_name')} {u.get('last_name')}" == "Ledger System"), None)
    if ledger_system_user:
        ledger_system_wallets = wallet_lib_api.list_wallets_by_user(node_context.wallet_service, ledger_system_user['user_id'])
        for wallet in ledger_system_wallets:
            if wallet['wallet_type'] in ['pool', 'burn']:
                wallet_name = wallet['wallet_type']
                current_user_balances[wallet_name] = {
                    "user_id": wallet_name,
                    "name": f"System {wallet_name.capitalize()} Wallet",
                    "total_balance": wallet.get('balance', 0.0)
                }

    current_ledger_summary = postprocess_lib_api.get_ledger_summary({0: node_context}) # Pass as dict for compatibility

    if not is_final_summary:
        print(f"\n--- {header} ---")
        before_state_summary['users'] = {uid: summary for uid, summary in current_user_balances.items()}
        before_state_summary['ledger'] = current_ledger_summary

        for user in sorted(current_user_balances.values(), key=lambda u: u['name']):
            print(f"  👤 {user['name']:<22} | Balance: {user['total_balance']:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")
        print("--------------------------------------------------")
        print(f"  📊 Total Ledger Balance: {current_ledger_summary['total_balance']:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")
        print("--------------------------------------------------\n")
    else:
        print(f"\n--- {header} ---")
        print(f"{'👤 User':<22} | {'Before':>18} | {'After':>18} | {'Change':>18}")
        print("-" * 80)

        sorted_users = sorted(current_user_balances.values(), key=lambda u: u['name'])

        for user_summary in sorted_users:
            uid = user_summary['user_id']
            name = user_summary['name']
            before_balance = before_state_summary.get('users', {}).get(uid, {}).get('total_balance', 0.0)
            after_balance = user_summary['total_balance']
            change = after_balance - before_balance

            print(
                f"{name:<22} | {before_balance:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {after_balance:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {change:+18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f}")

        print("-" * 80)

        before_ledger = before_state_summary.get('ledger', {})
        before_total = before_ledger.get('total_balance', 0.0)
        after_total = current_ledger_summary['total_balance']
        total_change = after_total - before_total

        print(
            f"{'📊 Total Ledger Balance':<22} | {before_total:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {after_total:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {total_change:+18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f}")
        print("-" * 80)


async def bootstrap_bachicoin() -> crossmodule_lib_api.NodeContext:
    """Sets up the test environment by bootstrapping a single node."""
    print("INFO: Setting up test environment...")

    print("\n🧹 Cleaning up old node directory...")
    d = dirs.base
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)

    print("✅ Test environment reset.")

    print(f"\n🚀 Launching single node...")
    # Use node_id 0 and a dummy port, as networking is removed
    node_context = await bootstrap_lib_api.bootstrap_singlenode(0, 9333, dirs) 

    print(f"✅ Single node bootstrapped successfully.")
    return node_context


async def main():
    """Main orchestrator function."""
    print("--- Starting BachiCoin Single Node Test ---")
    address_book = bootstrap_lib_api.GlobalAddressBook(storage_path=str(get_address_book_path(dirs.base)))
    node_context: crossmodule_lib_api.NodeContext = None # Initialize as single NodeContext
    in_memory_private_key_map: Dict[str, str] = {}

    try:
        node_context = await bootstrap_bachicoin()

        # --- Initialize services for the node context ---
        print("\nINFO: Initializing services for the node...")
        crossmodule_lib_api.initialize_node_context_services(node_context)
        print("✅ Services initialized for the node.")

        # --- Genesis Block Creation ---
        print("\nINFO: Creating Genesis Block...")
        if not blockchain_lib_api.get_block_by_height(node_context.blockchain_service, 0):
            genesis_data = blockchain_lib_api.prepare_genesis_block_data("testnet")
            genesis_hash = blockchain_lib_api.create_block_with_index(node_context.blockchain_service, genesis_data)
            blockchain_lib_api.set_chain_tip(node_context.blockchain_service, genesis_hash, 0)
            print(f"  🪙 Node: Created genesis block {genesis_hash[:12]}...")
        
        # --- System Identity Bootstrapping ---
        print("\nINFO: Bootstrapping System Identities...")
        addr_map, key_map = await bootstrap_lib_api.create_and_map_users_and_wallets(
            node_context, bootstrap_lib_api.BOOTSTRAP_USERS
        )
        node_context.address_map = addr_map
        setattr(node_context, 'private_key_map', key_map)
        
        for user_key, pub_address in addr_map.items():
            address_book.update_global_address_book(user_key, pub_address)
        in_memory_private_key_map.update(key_map)
        print("✅ System Identities Bootstrapped.")

        # --- Validator Registration ---
        print("\nINFO: Registering Validators...")
        users_on_node = node_context.user_service.list_users()
        bootstrap_lib_api.bootstrap_register_validators(node_context, users_on_node, node_context.address_map)
        print("✅ Validators Registered.")

        # --- Ledger Bootstrap (Genesis Mint Transaction) ---
        print("\nINFO: Bootstrapping Ledger (Genesis Mint Transaction)...")
        await bootstrap_lib_api.bootstrap_ledger(node_context=node_context)
        print("✅ Ledger Bootstrapped.")

        # --- Validator Confirmation ---
        print("\nINFO: Confirming Validator Registration...")
        validators = node_context.validator_service.get_active_validators()
        assert validators, f"[BOOT] Node: No active validators found!"
        print(f"  👷 Node: Validators active: {[v for v in validators]}")
        print("✅ Validator Registration Confirmed.")


        print("\nINFO: Creating individual users and updating maps...")
        for user_profile in REGULAR_USERS:
            # All users are on the single node (node_id 0)
            user_map, key_map = await bootstrap_lib_api.create_and_map_users_and_wallets(node_context, [user_profile])
            for user_key, pub_address in user_map.items():
                address_book.update_global_address_book(user_key, pub_address)
            in_memory_private_key_map.update(key_map)
        print("✅ Individual users added.")

        # The test now uses the single node context for summaries
        capture_or_display_summary(node_context, "SYSTEM STATE BEFORE TEST")

        # --- World Clock Transaction Submission and Consensus ---
        print("\nINFO: --- Starting World Clock Transaction Submission and Consensus ---")
        transactions_by_slot: Dict[int, List[Dict[str, Any]]] = {}
        for tx_template in TRANSACTION_SCHEDULE:
            slot = tx_template.get('slot', 0)
            if slot not in transactions_by_slot:
                transactions_by_slot[slot] = []
            transactions_by_slot[slot].append(tx_template)
        
        for current_slot in range(1, TARGET_SLOTS + 1):
            print(f"\n--- World Clock: Processing Slot {current_slot} ---")

            txs_for_this_slot = transactions_by_slot.get(current_slot, [])
            if txs_for_this_slot:
                print(f"  -> Submitting {len(txs_for_this_slot)} transactions for Slot {current_slot}...")
                txs_by_user_for_slot: Dict[str, List[Dict[str, Any]]] = {}
                for tx_template in txs_for_this_slot:
                    from_ref = tx_template.get("from_ref")
                    user_name = from_ref["user"] if from_ref else "Ledger System"
                    if user_name not in txs_by_user_for_slot:
                        txs_by_user_for_slot[user_name] = []
                    txs_by_user_for_slot[user_name].append(tx_template)

                for user_name, tx_list in txs_by_user_for_slot.items():
                    # All transactions are submitted to the single node
                    await tx_lib_api.submit_txs_for_user(
                        node_context=node_context,
                        user_name=user_name,
                        user_tx_templates=tx_list,
                        global_address_book=address_book.get_all_addresses(),
                        pvt_key_map=in_memory_private_key_map
                    )
            else:
                print(f"  -> No transactions scheduled for Slot {current_slot}.")

            print(f"  -> Driving consensus for Slot {current_slot}...")
            # drive_consensus_on_all_nodes expects a list of node contexts
            async for _ in consensus_lib_api.drive_consensus_on_all_nodes([node_context], slots_to_run_per_node=1):
                pass

            await check_for_background_exceptions()

        print("\nINFO: --- World Clock Simulation Complete ---")

        # --- FINAL POST-PROCESSING STEP ---
        print("\nINFO: --- Running Final Post-Processing Step ---")
        single_node_address_to_node_map = {addr: 0 for addr in address_book.get_all_addresses().values()}
        postprocess_lib_api.run_postprocess({0: node_context}, single_node_address_to_node_map)
        print("✅ Final Post-Processing Complete.")

        capture_or_display_summary(node_context, "SYSTEM STATE AFTER TEST", is_final_summary=True)
        
        # --- Add the new per-node summary ---
        display_per_node_summary(node_context)

    finally:
        print("\n--- BachiCoin Single Node Test Finished ---")
        if node_context:
            postprocess_lib_api.close_services({0: node_context}) # close_services expects a dict
        print(f"INFO: Global address book is preserved at: {address_book.storage_path}")


if __name__ == "__main__":
    asyncio.run(main())
