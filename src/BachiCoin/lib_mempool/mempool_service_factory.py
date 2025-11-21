#!/usr/bin/env python3
"""mempool_service_factory.py - creates a MempoolIndexService using a unified storage backend with dependency injection"""

from typing import Optional, Callable, Awaitable, Dict, Union, Any

from BachiCoin.lib_mempool.mempool_storage_factory import MempoolStorageFactory
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_mempool.mempool_config import MempoolMetrics, validate_mempool_transaction
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.lib_crossmodule.dirs import Dirs
from BachiCoin.lib_nonce import nonce as nonce_service


class MempoolServiceFactory:
    """Factory to create MempoolIndexService with its dependencies."""

    @staticmethod
    def create_mempool_index_service(
        node_context: Union[NodeContext, Dirs, Any],
        broadcast_func: Optional[Callable[[Dict[str, Any], Dict[str, Any]],
        Awaitable[Any]]] = None,
    ) -> MempoolIndexService:
        """
        Creates a MempoolIndexService.
        - Accepts either Dirs (via decorator) or NodeContext directly.
        - If NodeContext is None, constructs a minimal one from dirs.
        """

        # Ensure node_context
        ctx = adapt_context(node_context)

        # Construct storage adapter using dirs
        storage_adapter = MempoolStorageFactory.create_mempool_storage(ctx.node_dirs)

        # Construct the service
        service = MempoolIndexService(
            storage_adapter=storage_adapter,
            nonce_service=nonce_service,
            validator_func=validate_mempool_transaction,
            priority_scorer_func=MempoolMetrics.calculate_priority_score,
            node_context=ctx,
            network_broadcaster=broadcast_func
        )
        return service


# =================== SMOKE TEST ===================

if __name__ == "__main__":
    import asyncio
    from tests.test_config import dirs
    from BachiCoin.lib_network.net_protocol import MessageType
    from BachiCoin.lib_user.user_service_factory import UserServiceFactory
    from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
    from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory


    async def mock_broadcast_func(msg_type: MessageType, payload: Dict[str, Any]) -> None:
        print(f"Mock broadcast called: Type={msg_type.value}, Payload={payload.get('tx_hash', 'no_hash')[:8]}...")
        await asyncio.sleep(0.01)


    # Mock NodeContext for the factory's smoke test
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                user_service=UserServiceFactory.create_user_index_service(dirs),
                wallet_service=WalletServiceFactory.create_wallet_index_service(dirs),
                blockchain_service=BlockchainServiceFactory.create_blockchain_index_service(dirs),
                node_dirs=dirs,
                port=0, network="testnet", currency="BACHI"
            )


    mock_node_context = MockNodeContext(dirs)

    print("--- Testing factory with injected services ---")

    mempool_service_injected = MempoolServiceFactory.create_mempool_index_service(
        mock_node_context,
        broadcast_func=mock_broadcast_func
    )

    assert mempool_service_injected.node_context is mock_node_context
    print("✅ Factory correctly used injected node_context instance.")

    assert mempool_service_injected.network_broadcaster is mock_broadcast_func
    print("✅ Factory correctly injected the broadcast_func.")

    print("\n--- Smoke Test Passed ---")
