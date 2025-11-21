#!/usr/bin/env python3
"""
proposer_service_factory.py - A factory for creating a ProposerIndexService with all its dependencies injected"""

from typing import Optional, Union, Any

from BachiCoin.lib_proposer.proposer_storage_factory import ProposerStorageFactory
from BachiCoin.lib_proposer.proposer_index_service import ProposerIndexService
from BachiCoin.lib_mempool.mempool_service_factory import MempoolServiceFactory
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.lib_crossmodule.dirs import Dirs


class ProposerServiceFactory:
    """Factory to create a ProposerIndexService with dependency injection."""

    @staticmethod
    def create_proposer_index_service(
        node_context: Union[NodeContext, Dirs, Any],
        mempool_service: Optional[MempoolIndexService] = None,
        validator_service: Optional[ValidatorIndexService] = None,
        blockchain_service: Optional[BlockchainIndexService] = None
    ) -> ProposerIndexService:
        """
        Creates a ProposerIndexService, allowing service injection.
        Accepts either a Dirs object or a NodeContext object.
        """
        ctx = adapt_context(node_context)

        mempool_service_to_use = mempool_service or MempoolServiceFactory.create_mempool_index_service(ctx)
        validator_service_to_use = validator_service or ValidatorServiceFactory.create_validator_index_service(ctx)
        blockchain_service_to_use = blockchain_service or BlockchainServiceFactory.create_blockchain_index_service(ctx)

        proposer_storage_adapter = ProposerStorageFactory.create_proposer_storage(ctx.node_dirs)
        service = ProposerIndexService(
            storage_adapter=proposer_storage_adapter,
            validator_index_service=validator_service_to_use,
            mempool_index_service=mempool_service_to_use,
            blockchain_index_service=blockchain_service_to_use
        )
        return service


if __name__ == "__main__":
    from tests.test_config import dirs


    # Mock NodeContext for the factory's smoke test
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                mempool_service=MempoolServiceFactory.create_mempool_index_service(dirs),
                validator_service=ValidatorServiceFactory.create_validator_index_service(dirs),
                blockchain_service=BlockchainServiceFactory.create_blockchain_index_service(dirs),
                node_dirs=dirs,
                port=0, network="testnet", currency="BACHI"
            )

    mock_node_context = MockNodeContext(dirs)

    # Test default behavior
    proposer_service_default = ProposerServiceFactory.create_proposer_index_service(mock_node_context)
    print(f"✅ {proposer_service_default} created with default dependencies.")

    # Test with injected services
    injected_mempool = MempoolServiceFactory.create_mempool_index_service(mock_node_context)
    proposer_service_injected = ProposerServiceFactory.create_proposer_index_service(
        mock_node_context, mempool_service=injected_mempool
    )
    assert proposer_service_injected.mempool_index_service is injected_mempool
    print("✅ Factory correctly used injected mempool_service instance.")

    print("--- Smoke Test Passed ---")
