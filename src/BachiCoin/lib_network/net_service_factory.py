#!/usr/bin/env python3
"""net_service_factory.py - creates network nodes with plug-and-play adapters."""

import asyncio
from typing import Dict, Any

from BachiCoin.lib_network.net_storage_factory import NetStorageFactory
from BachiCoin.lib_network.net_index_service import NetIndexService
from BachiCoin.lib_network.net_validation import NetValidation
from BachiCoin.lib_crossmodule.dirs import Dirs
from BachiCoin.lib_network.net_node import NetNode
from BachiCoin.lib_network.net_base_adapter import NetBaseAdapter
from BachiCoin.lib_network.p2p_adapter import P2PAdapter
from BachiCoin.lib_network.loopback_adapter import LoopbackAdapter
from BachiCoin.lib_network.net_config import NodeType
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_network.net_protocol import MessageType


class NetServiceFactory:
    """Factory to create network services and nodes with their dependencies."""

    @staticmethod
    def create_net_index_service(dirs: Dirs) -> NetIndexService:
        """Creates NetIndexService using a unified storage backend."""
        storage_adapter = NetStorageFactory.create_net_storage(dirs)
        peer_validator = NetValidation.validate_peer_data
        service = NetIndexService(
            storage_adapter=storage_adapter,
            peer_validator_func=peer_validator
        )
        service.initialize()
        return service

    @staticmethod
    def create_net_node(dirs: Dirs, host: str, port: int, mempool_service: MempoolIndexService, adapter_type: str = "loopback") -> NetNode:
        """Factory function to create a NetNode with a selectable network adapter."""
        print(f"  [Factory] INFO: Creating node with '{adapter_type}' adapter.")
        net_service = NetServiceFactory.create_net_index_service(dirs)
        
        node_data = {
            "node_url": f"{host}:{port}",
            "ip_address": host,
            "p2p_port": port,
            "node_type": NodeType.FULL_NODE.value,
        }
        node_id = net_service.register_node_with_index(node_data)
        
        adapter: NetBaseAdapter
        if adapter_type == "p2p":
            adapter = P2PAdapter(host, port, node_id)
        elif adapter_type == "loopback":
            adapter = LoopbackAdapter(node_id)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")
        
        # The NetNode now receives all its dependencies directly.
        node = NetNode(dirs, adapter, net_service, node_id, mempool_service) # Re-added mempool_service
        return node


if __name__ == "__main__":
    """Simple smoke test to verify the factory's flexibility."""
    from tests.test_config import dirs
    from BachiCoin.lib_network.loopback_adapter import LOOPBACK_REGISTRY
    from BachiCoin.lib_mempool.mempool_config import MempoolMetrics, validate_mempool_transaction
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_nonce import nonce as nonce_service
    from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory # Direct import
    from BachiCoin.lib_crossmodule.node_context import NodeContext


    async def smoke_test_net_factory():
        print("--- Running NetServiceFactory Smoke Test ---")

        # Create mock mempool service for testing
        class MockMempoolStorageAdapter:
            def __init__(self, dirs): pass
            def save_mempool_state(self, state): pass
            def load_mempool_state(self): return None
            def close(self): pass
        
        # Create real service instances for the NodeContext
        real_user_service = UserServiceFactory.create_user_index_service(dirs)
        real_wallet_service = WalletServiceFactory.create_wallet_index_service(dirs, user_service=real_user_service)
        real_blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(dirs)

        # Create a NodeContext instance to pass to MempoolIndexService
        mock_node_context = NodeContext(
            user_service=real_user_service,
            wallet_service=real_wallet_service,
            blockchain_service=real_blockchain_service,
            node_dirs=dirs,
            port=0, network="testnet", currency="BACHI" # Populate minimal config
        )

        async def mock_broadcast_func(msg_type: MessageType, payload: Dict[str, Any]) -> None:
            print(f"Mock broadcast called: Type={msg_type.value}, Payload={payload.get('tx_hash', 'no_hash')[:8]}...")
            await asyncio.sleep(0.01)

        mock_storage = MockMempoolStorageAdapter(dirs)
        
        # Instantiate MempoolIndexService with the NodeContext
        mock_mempool_service = MempoolIndexService(
            storage_adapter=mock_storage,
            nonce_service=nonce_service,
            validator_func=validate_mempool_transaction,
            priority_scorer_func=MempoolMetrics.calculate_priority_score,
            node_context=mock_node_context, # Pass the NodeContext
            network_broadcaster=mock_broadcast_func
        )

        # 1. Test Loopback Node creation (default)
        print("\n--- Testing Node with Loopback Adapter (Default) ---")
        LOOPBACK_REGISTRY.clear() # Ensure a clean state
        node_loopback = NetServiceFactory.create_net_node(dirs, "127.0.0.1", 9998, mock_mempool_service)
        print(f"✅ Node created successfully with ID: {node_loopback.node_id}")
        assert isinstance(node_loopback.network_adapter, LoopbackAdapter)
        await node_loopback.start()
        await node_loopback.stop()
        print("✅ Loopback node lifecycle tested.")

        # 2. Test P2P Node creation (explicit)
        print("\n--- Testing Node with P2P Adapter ---")
        node_p2p = NetServiceFactory.create_net_node(dirs, "127.0.0.1", 9999, mock_mempool_service, adapter_type="p2p")
        print(f"✅ Node created successfully with ID: {node_p2p.node_id}")
        assert isinstance(node_p2p.network_adapter, P2PAdapter)
        await node_p2p.start()
        await node_p2p.stop()
        print("✅ P2P node lifecycle tested.")

        print("\n--- NetServiceFactory Smoke Test Passed! ---")

    asyncio.run(smoke_test_net_factory())
