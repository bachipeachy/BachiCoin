#!/usr/bin/env python3
"""
finalizer_service_factory.py - A factory for creating a FinalizerIndexService with all its dependencies injected"""

from typing import Optional, Union, Any

from BachiCoin.lib_finalizer.finalizer_storage_factory import FinalizerStorageFactory
from BachiCoin.lib_finalizer.finalizer_index_service import FinalizerIndexService
from BachiCoin.lib_attestor.attestor_service_factory import AttestorServiceFactory
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_attestor.attestor_index_service import AttestorIndexService
from BachiCoin.lib_blockchain.blockchain_index_service import BlockchainIndexService
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.lib_crossmodule.dirs import Dirs


class FinalizerServiceFactory:
    """Factory to create a FinalizerIndexService with dependency injection."""

    @staticmethod
    def create_finalizer_index_service(
        node_context: Union[NodeContext, Dirs, Any],
        attestor_service: Optional[AttestorIndexService] = None,
        blockchain_service: Optional[BlockchainIndexService] = None,
        validator_service: Optional[ValidatorIndexService] = None
    ) -> FinalizerIndexService:
        """
        Creates a FinalizerIndexService, allowing service injection.
        Accepts either a Dirs object or a NodeContext object.
        """
        ctx = adapt_context(node_context)

        attestor_service_to_use = attestor_service or AttestorServiceFactory.create_attestor_index_service(ctx)
        blockchain_service_to_use = blockchain_service or BlockchainServiceFactory.create_blockchain_index_service(ctx)
        validator_service_to_use = validator_service or ValidatorServiceFactory.create_validator_index_service(ctx)

        finalizer_storage_adapter = FinalizerStorageFactory.create_finalizer_storage(ctx.node_dirs)
        service = FinalizerIndexService(
            storage_adapter=finalizer_storage_adapter,
            attestor_index_service=attestor_service_to_use,
            blockchain_index_service=blockchain_service_to_use,
            validator_index_service=validator_service_to_use
        )
        return service


if __name__ == "__main__":
    from tests.test_config import dirs

    # Mock NodeContext for the factory's smoke test
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                attestor_service=AttestorServiceFactory.create_attestor_index_service(dirs),
                blockchain_service=BlockchainServiceFactory.create_blockchain_index_service(dirs),
                validator_service=ValidatorServiceFactory.create_validator_index_service(dirs),
                node_dirs=dirs
            )

    mock_node_context = MockNodeContext(dirs)

    # Test default behavior
    finalizer_service_default = FinalizerServiceFactory.create_finalizer_index_service(mock_node_context)
    print(f"✅ {finalizer_service_default} created with default dependencies.")

    # Test with injected services
    injected_attestor = AttestorServiceFactory.create_attestor_index_service(mock_node_context)
    injected_blockchain = BlockchainServiceFactory.create_blockchain_index_service(mock_node_context)
    injected_validator = ValidatorServiceFactory.create_validator_index_service(mock_node_context)
    
    finalizer_service_injected = FinalizerServiceFactory.create_finalizer_index_service(
        mock_node_context,
        attestor_service=injected_attestor,
        blockchain_service=injected_blockchain,
        validator_service=injected_validator
    )
    assert finalizer_service_injected.attestor_index_service is injected_attestor
    assert finalizer_service_injected.blockchain_index_service is injected_blockchain
    assert finalizer_service_injected.validator_index_service is injected_validator
    print("✅ Factory correctly used injected service instances.")

    print("--- Smoke Test Passed ---")
