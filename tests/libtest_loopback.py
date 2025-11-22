"""Orchestrator for end-to-end loopback testing."""
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

from BachiCoin.api_public import (
    user_lib_api,
    wallet_lib_api,
    blockchain_lib_api,
    postprocess_lib_api,
    net_lib_api,
    bootstrap_lib_api,
    tx_lib_api,
    consensus_lib_api,
    crossmodule_lib_api,
)
from tests.libtest_data import REGULAR_USERS, TRANSACTION_SCHEDULE, calculate_ground_truth_balances
from tests.test_config import all_node_dirs

# --- Test Configuration ---
TARGET_SLOTS = 64 # Increased to match onenode test
ports = [9333, 9334, 9335, 9336, 9337]

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


def display_per_node_summary(all_node_contexts: Dict[int, crossmodule_lib_api.NodeContext]):
    """Displays a detailed state summary for each individual node."""
    print("\n" + "=" * 80)
    print("--- PER-NODE STATE SUMMARY ---")
    print("=" * 80)

    for node_id, node_context in sorted(all_node_contexts.items()):
        print(f"\n--- Node {node_id} State ---")

        local_users = user_lib_api.list_users(node_context.user_service)
        local_wallets = wallet_lib_api.list_wallets(node_context.wallet_service)

        local_total_balance = sum(w.get('balance', 0.0) for w in local_wallets)

        print(f"  👥 Local Users: {len(local_users)}")
        for user in local_users:
            user_balance = sum(w.get('balance', 0.0) for w in local_wallets if w.get('user_id') == user['user_id'])
            print(
                f"    - {user.get('first_name')} {user.get('last_name')}: {user_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")

        print(
            f"  💰 Local Ledger Balance: {local_total_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI in {len(local_wallets)} wallets.")

    print("\n" + "=" * 80)


def capture_or_display_summary(
        all_node_contexts: Dict[int, crossmodule_lib_api.NodeContext],
        header: str,
        is_final_summary: bool = False,
        expected_balances: Optional[Dict[str, Dict[str, float]]] = None
):
    """Captures the initial system state or displays a before-and-after comparison across all nodes."""
    global before_state_summary

    # --- 1. Get Current State ---
    all_users = []
    all_user_ids = set()
    for node_context in all_node_contexts.values():
        for user in user_lib_api.list_users(node_context.user_service):
            if user['user_id'] not in all_user_ids:
                all_users.append(user)
                all_user_ids.add(user['user_id'])

    current_user_wallets = {}
    for user in all_users:
        user_name = f"{user.get('first_name')} {user.get('last_name')}"
        current_user_wallets[user_name] = {}
        # A user's wallets can be on different nodes, so we must check all of them
        for node_context in all_node_contexts.values():
            user_on_node = user_lib_api.get_user(node_context.user_service, user['user_id'])
            if user_on_node:
                user_wallets = wallet_lib_api.list_wallets_by_user(node_context.wallet_service, user['user_id'])
                for wallet in user_wallets:
                    current_user_wallets[user_name][wallet['wallet_type']] = wallet.get('balance', 0.0)

    # --- 2. Display Logic ---
    if not is_final_summary:
        print(f"\n--- {header} ---")
        before_state_summary['users'] = {}
        for user_name, wallets in current_user_wallets.items():
            total_balance = sum(wallets.values())
            before_state_summary['users'][user_name] = total_balance
            print(f"  👤 {user_name:<22} | Balance: {total_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")
        
        total_ledger_balance = sum(before_state_summary['users'].values())
        print("--------------------------------------------------")
        print(f"  📊 Total Ledger Balance: {total_ledger_balance:.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} BACHI")
        print("--------------------------------------------------\n")
    else:
        print(f"\n--- {header} ---")
        print(f"{'👤 User /  Wallet':<28} | {'Actual':>18} | {'Expected':>18} | {'Diff':>18}")
        print("-" * 88)

        total_actual = 0.0
        total_expected = 0.0

        for user_name in sorted(current_user_wallets.keys()):
            wallets = current_user_wallets[user_name]
            user_actual_total = sum(wallets.values())
            user_expected_total = sum(expected_balances.get(user_name, {}).values()) if expected_balances else 0.0
            
            print(f"👤 {user_name:<25} | {user_actual_total:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {user_expected_total:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {'':>18}")

            for wallet_type in sorted(wallets.keys()):
                actual_balance = wallets[wallet_type]
                expected_balance = expected_balances.get(user_name, {}).get(wallet_type, 0.0) if expected_balances else 0.0
                diff = actual_balance - expected_balance
                
                diff_str = f"{diff:+.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f}"
                if abs(diff) > 1e-9:
                    diff_str = f"❌ {diff_str}"

                print(f"  - {wallet_type:<23} | {actual_balance:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {expected_balance:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {diff_str}")
            
            total_actual += user_actual_total
            total_expected += user_expected_total
        
        print("-" * 88)
        total_diff = total_actual - total_expected
        total_diff_str = f"{total_diff:+.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f}"
        if abs(total_diff) > 1e-9:
            total_diff_str = f"❌ {total_diff_str}"
            
        print(f"{'📊 Total Ledger Balance':<28} | {total_actual:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {total_expected:18,.{postprocess_lib_api.DISPLAY_DECIMAL_PLACES}f} | {total_diff_str}")
        print("-" * 88)


async def bootstrap_bachicoin(address_book: bootstrap_lib_api.GlobalAddressBook) -> Dict[int, crossmodule_lib_api.NodeContext]:
    """Sets up the test environment by bootstrapping all nodes."""
    print("INFO: Setting up test environment...")
    num_nodes = len(ports)

    print("\n🧹 Cleaning up old node directories...")
    for i in range(num_nodes):
        d = all_node_dirs[i].base
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    address_book.clear()
    print("✅ Test environment reset.")

    print(f"\n🚀 Launching {num_nodes} nodes...")
    node_tasks = [
        asyncio.create_task(bootstrap_lib_api.bootstrap_singlenode(i, ports[i], all_node_dirs[i]))
        for i in range(num_nodes)
    ]
    results = await asyncio.gather(*node_tasks)
    nodes_data: Dict[int, crossmodule_lib_api.NodeContext] = {i: node_context for i, node_context in enumerate(results)}

    # Services are no longer initialized here; they are initialized in main()
    print(f"✅ All {num_nodes} nodes bootstrapped successfully.")
    return nodes_data


async def main():
    """Main orchestrator function."""
    print("--- Starting BachiCoin Loopback Test ---")
    address_book = bootstrap_lib_api.GlobalAddressBook(storage_path=str(get_address_book_path(all_node_dirs[0].base)))
    nodes_data: Dict[int, crossmodule_lib_api.NodeContext] = {}
    address_to_node_map: Dict[str, int] = {}
    in_memory_private_key_map: Dict[str, str] = {}  # Initialize here

    try:
        nodes_data = await bootstrap_bachicoin(address_book)

        # --- Initialize services for each node context ---
        print("\nINFO: Initializing services for each node...")
        for node_id, node_context in nodes_data.items():
            crossmodule_lib_api.initialize_node_context_services(node_context)
            print(f"  [DEBUG] Node {node_id}: user_service ID: {id(node_context.user_service)}")
            print(f"  [DEBUG] Node {node_id}: wallet_service ID: {id(node_context.wallet_service)}")
        print("✅ Services initialized for all nodes.")

        # --- Re-integrate Genesis Block Creation ---
        print("\nINFO: Creating Genesis Blocks...")
        for node_id, node_context in nodes_data.items():
            if not blockchain_lib_api.get_block_by_height(node_context.blockchain_service, 0):
                genesis_data = blockchain_lib_api.prepare_genesis_block_data("testnet")
                genesis_hash = blockchain_lib_api.create_block_with_index(node_context.blockchain_service, genesis_data)
                blockchain_lib_api.set_chain_tip(node_context.blockchain_service, genesis_hash, 0)
                print(f"  🪙 Node {node_id}: Created genesis block {genesis_hash[:12]}...")

        # --- Re-integrate Network Service Setup ---
        print("\nINFO: Setting up network services...")
        for node_id, node_context in nodes_data.items():
            network_service = net_lib_api.create_net_node(
                dirs=node_context.node_dirs,
                host="127.0.0.1",
                port=node_context.port,
                mempool_service=node_context.mempool_service,
                adapter_type="loopback"  # Assuming loopback for this test
            )
            await network_service.start()
            node_context.network_service = network_service
            # Inject the network broadcaster into the mempool service
            node_context.mempool_service.network_broadcaster = network_service.broadcast
        print("✅ Network services started for all nodes.")

        # --- Re-integrate System Identity Bootstrapping ---
        print("\nINFO: Bootstrapping System Identities...")
        # First, create system users on Node 0 and capture their user_ids
        node_0_context = nodes_data[0]
        node_0_system_user_map, node_0_system_key_map = await bootstrap_lib_api.create_and_map_users_and_wallets(
            node_0_context, bootstrap_lib_api.BOOTSTRAP_USERS
        )
        system_user_ids: Set[str] = set(node_0_system_user_map.keys())

        # Now, iterate through all nodes to complete bootstrapping and build the address_to_node_map
        for node_id, node_context in nodes_data.items():
            # If not Node 0, create users on this node too (they will have same user_ids/addresses)
            if node_id != 0:
                addr_map, key_map = await bootstrap_lib_api.create_and_map_users_and_wallets(
                    node_context, bootstrap_lib_api.BOOTSTRAP_USERS
                )
            else:
                addr_map = node_0_system_user_map
                key_map = node_0_system_key_map

            node_context.address_map = addr_map
            setattr(node_context, 'private_key_map', key_map)

            for user_key, pub_address in addr_map.items():
                address_book.update_global_address_book(user_key, pub_address)
                # FIX: Use system_user_ids to correctly map system/staker addresses to Node 0
                if user_key in system_user_ids:
                    address_to_node_map[pub_address] = 0
                else:
                    address_to_node_map[pub_address] = node_id
            in_memory_private_key_map.update(key_map)
        print("✅ System Identities Bootstrapped.")

        # --- Re-integrate Validator Registration ---
        print("\nINFO: Registering Validators...")
        for node_id, node_context in nodes_data.items():
            users_on_node = node_context.user_service.list_users()
            bootstrap_lib_api.bootstrap_register_validators(node_context, users_on_node, node_context.address_map)
        print("✅ Validators Registered.")

        # --- Re-integrate Ledger Bootstrap (Genesis Mint Transaction) ---
        print("\nINFO: Bootstrapping Ledger (Genesis Mint Transaction)...")
        for node_id, node_context in nodes_data.items():
            await bootstrap_lib_api.bootstrap_ledger(node_context=node_context)
        print("✅ Ledger Bootstrapped.")

        # --- Re-integrate Validator Confirmation ---
        print("\nINFO: Confirming Validator Confirmation...")
        for node_id, node_context in nodes_data.items():
            validators = node_context.validator_service.get_active_validators()
            assert validators, f"[BOOT] Node {node_id}: No active validators found!"
            print(f"  👷 Node {node_id}: Validators active: {[v for v in validators]}")
        print("✅ Validator Registration Confirmed.")

        print("\nINFO: Creating individual users and updating maps...")
        for user_profile in REGULAR_USERS:
            home_node_id = user_profile["home_node"]
            home_node_context = nodes_data.get(home_node_id)
            if not home_node_context:
                continue
            user_map, key_map = await bootstrap_lib_api.create_and_map_users_and_wallets(home_node_context, [user_profile])
            for user_key, pub_address in user_map.items():
                address_book.update_global_address_book(user_key, pub_address)
                address_to_node_map[pub_address] = home_node_id  # Regular users map to their home node
            in_memory_private_key_map.update(key_map)
        print("✅ Individual users added.")

        # The test now uses the complete set of node contexts for summaries
        capture_or_display_summary(nodes_data, "SYSTEM STATE BEFORE TEST")

        # --- World Clock Transaction Submission and Consensus ---
        print("\nINFO: --- Starting World Clock Transaction Submission and Consensus ---")
        transactions_by_slot: Dict[int, List[Dict[str, Any]]] = {}
        for tx_template in TRANSACTION_SCHEDULE:
            slot = tx_template.get('slot', 0)
            if slot not in transactions_by_slot:
                transactions_by_slot[slot] = []
            transactions_by_slot[slot].append(tx_template)

        user_home_node_map: Dict[str, int] = {p["name"]: p["home_node"] for p in REGULAR_USERS}
        # System and staker names are already handled in address_to_node_map construction

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
                    home_node_id = user_home_node_map.get(user_name, 0)
                    submitter_node_context = nodes_data[home_node_id]
                    await tx_lib_api.submit_txs_for_user(
                        node_context=submitter_node_context,
                        user_name=user_name,
                        user_tx_templates=tx_list,
                        global_address_book=address_book.get_all_addresses(),
                        pvt_key_map=in_memory_private_key_map
                    )
            else:
                print(f"  -> No transactions scheduled for Slot {current_slot}.")

            print(f"  -> Driving consensus for Slot {current_slot}...")
            async for _ in consensus_lib_api.drive_consensus_on_all_nodes(list(nodes_data.values()), slots_to_run_per_node=1):
                pass

            await check_for_background_exceptions()

        print("\nINFO: --- World Clock Simulation Complete ---")
        
        # --- FINAL POST-PROCESSING STEP ---
        print("\nINFO: --- Running Final Post-Processing Step ---")
        postprocess_lib_api.run_postprocess(nodes_data, address_to_node_map)
        print("✅ Final Post-Processing Complete.")

        # Calculate ground truth balances
        expected_final_balances = calculate_ground_truth_balances()
        capture_or_display_summary(nodes_data, "SYSTEM STATE AFTER TEST", is_final_summary=True, expected_balances=expected_final_balances)

        # --- Add the new per-node summary ---
        display_per_node_summary(nodes_data)

    finally:
        print("\n--- BachiCoin Loopback Test Finished ---")
        if nodes_data:
            postprocess_lib_api.close_services(nodes_data)
            print("\n🛑 Shutting down network services...")
            for node_context in nodes_data.values():
                if node_context.network_service:
                    await node_context.network_service.stop()
            print("✅ All network nodes shut down cleanly.")

        print(f"INFO: Global address book is preserved at: {address_book.storage_path}")


if __name__ == "__main__":
    asyncio.run(main())
