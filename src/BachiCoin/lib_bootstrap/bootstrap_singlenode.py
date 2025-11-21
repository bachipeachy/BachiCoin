#!/usr/bin/env python3
"""bootstrap_singlenode.py -- Bootstraps a full single-node with multiple network transport adapter instantiations"""

import asyncio
import shutil
from typing import Dict, List

from BachiCoin.lib_crossmodule.crossmodule_config import NetworkType, Currency
from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_crossmodule.dirs import Dirs


async def bootstrap_singlenode(
        node_id: int,
        port: int,
        node_dirs: Dirs,
        network_adapter: str = "loopback",
) -> NodeContext:
    """Sequentially initialize and bootstrap a single node. """
    print(f"\n🚀 Node {node_id} (Port {port}): Starting bootstrap with {network_adapter} adapter...")

    # Create the NodeContext object (partially initialized - services are None)
    node_context = NodeContext(
        node_dirs=node_dirs,
        port=port,
        network=NetworkType.TESTNET.value,
        currency=Currency.BACHI.value
    )

    print(f"✅ Node {node_id}: Bootstrap complete and ready (services uninitialized).")
    return node_context


async def main(
        all_node_dirs: List[Dirs],
        node_ports: List[int],
        network_adapter: str = "loopback",
) -> Dict[int, NodeContext]:
    """Bootstraps multiple nodes, runs consensus, and shuts down cleanly."""
    print("=" * 70)
    print(f"🎯 BachiCoin Multi-Node Bootstrap Simulation (Adapter: {network_adapter})")
    print("=" * 70)

    print("\n🧹 Cleaning up old node directories...")
    for d in all_node_dirs:
        if d.base.exists():
            shutil.rmtree(d.base)
        d.ensure()
    print("✅ Test environment reset.")

    print("\n🚀 Launching nodes...")
    num_nodes = min(len(node_ports), len(all_node_dirs))

    node_tasks = [
        asyncio.create_task(
            bootstrap_singlenode(
                i, node_ports[i], all_node_dirs[i], network_adapter=network_adapter
            )
        )
        for i in range(num_nodes)
    ]
    results = await asyncio.gather(*node_tasks)

    nodes_data = {}
    for i, node_context in enumerate(results):
        nodes_data[i] = node_context

    print("✅ All nodes bootstrapped successfully.")

    print("\n🛑 Shutting down network services...")
    for node_context in nodes_data.values():
        if node_context.network_service:
            await node_context.network_service.stop()
    print("✅ All network nodes shut down cleanly.")

    return nodes_data


if __name__ == "__main__":
    import argparse
    from tests.test_config import all_node_dirs

    parser = argparse.ArgumentParser(description="BachiCoin Multi-Node Bootstrap Simulation")
    parser.add_argument("--adapter", type=str, default="loopback", choices=["loopback", "p2p"],
                        help="Network adapter to use ('loopback' or 'p2p')")
    args = parser.parse_args()

    ports = [9333, 9334, 9335, 9336, 9337]

    try:
        asyncio.run(main(all_node_dirs, ports, network_adapter=args.adapter))
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user.")
    finally:
        print("\n" + "=" * 70)
        print("🏁 SIMULATION ENDED")
        print("=" * 70)
