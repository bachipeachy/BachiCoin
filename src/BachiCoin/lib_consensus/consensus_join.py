#!/usr/bin/env python3
import asyncio
from typing import List, Dict, Any, AsyncGenerator

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_consensus.consensus import run_consensus


async def drive_consensus_on_all_nodes(
    node_contexts: List[NodeContext],
    slots_to_run_per_node: int,
) -> AsyncGenerator[Dict[int, List[Dict[str, Any]]], None]:
    """
    Drives the consensus process for a specified number of slots across all provided nodes.

    Args:
        node_contexts: A list of NodeContext objects, each representing a bootstrapped node.
        slots_to_run_per_node: The number of consensus slots to run for each node
                                during this invocation.

    Yields:
        A dictionary where keys are node IDs (indices in the node_contexts list)
        and values are lists of consensus slot results for that node.
    """
    # Removed: print(f"\n--- Driving consensus for {slots_to_run_per_node} slots on {len(node_contexts)} nodes ---")

    # Create a list of tasks, one for each node's consensus run
    consensus_tasks = []
    for i, node_context in enumerate(node_contexts):
        # Create a task to run consensus for this node
        # We need to collect all results from the generator
        async def run_single_node_consensus(node_id: int, nc: NodeContext):
            # Removed: print(f"  [Node {node_id}] Starting consensus for {slots_to_run_per_node} slots...")
            results = []
            for slot_result in run_consensus(
                nc, # Pass the NodeContext directly
                slots_to_run=slots_to_run_per_node,
            ):
                results.append(slot_result)
            # Removed: print(f"  [Node {node_id}] Finished consensus for {slots_to_run_per_node} slots.")
            return {node_id: results}

        consensus_tasks.append(run_single_node_consensus(i, node_context))

    # Run all node consensus tasks concurrently
    all_results = await asyncio.gather(*consensus_tasks)

    # Aggregate results for yielding

    aggregated_results = {}
    for res_dict in all_results:
        aggregated_results.update(res_dict)
    
    yield aggregated_results

    # Removed: print("--- Consensus drive completed for all nodes ---")

# Minimal smoke test (similar to existing bootstrap_singlenode main)
if __name__ == "__main__":
    from pathlib import Path
    import sys
    import shutil

    sys.path.append(str(Path(__file__).resolve().parents[3])) # Adjust path to reach BachiCoin root

    from tests.test_config import all_node_dirs
    from BachiCoin.lib_bootstrap.bootstrap_singlenode import bootstrap_singlenode
    from BachiCoin.lib_crossmodule.bachicoin_services import initialize_node_context_services

    async def main_smoke_test():
        print("=" * 70)
        print("🚀 Starting Smoke Test for consensus_join.py")
        print("=" * 70)

        # Setup: Bootstrap multiple nodes
        node_ports = [9333, 9334] # Using 2 nodes for a quick test
        num_nodes = len(node_ports)

        print("\n🧹 Cleaning up old node directories...")
        for d in all_node_dirs[:num_nodes]:
            if d.base.exists():
                shutil.rmtree(d.base)
            d.ensure()
        print("✅ Test environment reset.")

        print("\n🚀 Bootstrapping nodes...")
        bootstrapped_nodes = []
        for i in range(num_nodes):
            node_context = await bootstrap_singlenode(i, node_ports[i], all_node_dirs[i])
            bootstrapped_nodes.append(node_context)
        print("✅ All nodes bootstrapped successfully.")

        print("\n🔧 Initializing node services...")
        for node_context in bootstrapped_nodes:
            initialize_node_context_services(node_context)
        print("✅ All node services initialized.")

        # Execution: Drive consensus on all nodes
        print("\n--- Driving consensus for 2 slots on all nodes ---")
        all_consensus_results = []
        async for results_per_slot in drive_consensus_on_all_nodes(bootstrapped_nodes, slots_to_run_per_node=2):
            all_consensus_results.append(results_per_slot)
        
        # Verification
        print("\n--- Verifying consensus results ---")
        assert len(all_consensus_results) == 1 # Should yield once with all results
        assert len(all_consensus_results[0]) == num_nodes # Results for each node
        
        for node_id, node_slot_results in all_consensus_results[0].items():
            print(f"  [Node {node_id}] Processed {len(node_slot_results)} slots.")
            assert len(node_slot_results) == 2 # Each node should have run 2 slots
            for slot_res in node_slot_results:
                # Corrected assertion to handle both 'skipped' status and successful block_hash
                assert ('block_hash' in slot_res and slot_res['block_hash'] is not None) or (slot_res.get('status') == 'skipped')
                print(f"    Slot {slot_res['slot_processed']}: Block {slot_res.get('block_hash', 'skipped')[:12] if slot_res.get('block_hash') else 'skipped'} (Tx: {slot_res.get('transactions_included', 0)})")
        
        print("✅ Consensus results verified.")

        print("\n🛑 Shutting down network services...")
        for node_context in bootstrapped_nodes:
            if node_context.network_service:
                await node_context.network_service.stop()
        print("✅ All network nodes shut down cleanly.")

        print("=" * 70)
        print("🎉 Smoke Test for consensus_join.py PASSED")
        print("=" * 70)

    asyncio.run(main_smoke_test())
