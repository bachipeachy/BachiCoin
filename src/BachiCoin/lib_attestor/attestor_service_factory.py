#!/usr/bin/env python3
"""
attestor_service_factory.py - A factory for creating a AttestorIndexService with all its dependencies injected"""

from typing import Optional, Union, Any

from BachiCoin.lib_attestor.attestor_storage_factory import AttestorStorageFactory
from BachiCoin.lib_attestor.attestor_index_service import AttestorIndexService
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.lib_crossmodule.dirs import Dirs


class AttestorServiceFactory:
    """Factory to create a AttestorIndexService with dependency injection."""

    @staticmethod
    def create_attestor_index_service(
        node_context: Union[NodeContext, Dirs, Any],
        validator_service: Optional[ValidatorIndexService] = None
    ) -> AttestorIndexService:
        """Creates an AttestorIndexService, allowing validator_service injection."""
        ctx = adapt_context(node_context)

        validator_service_to_use = validator_service or ValidatorServiceFactory.create_validator_index_service(ctx)

        attestor_storage_adapter = AttestorStorageFactory.create_attestor_storage(ctx.node_dirs)
        service = AttestorIndexService(
            storage_adapter=attestor_storage_adapter,
            validator_index_service=validator_service_to_use,
        )
        return service


if __name__ == "__main__":
    from tests.test_config import dirs

    # Mock NodeContext for the factory's smoke test
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                validator_service=ValidatorServiceFactory.create_validator_index_service(dirs),
                node_dirs=dirs
            )

    mock_node_context = MockNodeContext(dirs)

    # Test default behavior
    attestor_service_default = AttestorServiceFactory.create_attestor_index_service(mock_node_context)
    print(f"✅ {attestor_service_default} created successfully.")

    # Test with injected service
    injected_validator = ValidatorServiceFactory.create_validator_index_service(mock_node_context)
    attestor_service_injected = AttestorServiceFactory.create_attestor_index_service(
        mock_node_context, validator_service=injected_validator
    )
    assert attestor_service_injected.validator_index_service is injected_validator
    print("✅ Factory correctly used injected validator_service instance.")

    print("--- Smoke Test Passed ---")
