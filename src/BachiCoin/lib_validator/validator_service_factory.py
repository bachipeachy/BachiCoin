#!/usr/bin/env python3
"""validator_service_factory.py - creates a ValidatorIndexService using a unified storage backend with dependency injection"""

from typing import Optional, Union, Any

from BachiCoin.lib_validator.validator_storage_factory import ValidatorStorageFactory
from BachiCoin.lib_validator.validator_index_service import ValidatorIndexService
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.lib_crossmodule.dirs import Dirs

class ValidatorServiceFactory:
    """Factory to create ValidatorIndexService with its dependencies."""

    @staticmethod
    def create_validator_index_service(
        node_context: Union[NodeContext, Dirs, Any],
        user_service: Optional[UserIndexService] = None,
        wallet_service: Optional[WalletIndexService] = None
    ) -> ValidatorIndexService:
        """
        Creates ValidatorIndexService, allowing injection of shared services.
        Accepts either a Dirs object or a NodeContext object.
        """
        ctx = adapt_context(node_context)

        user_service_to_use = user_service or UserServiceFactory.create_user_index_service(ctx)
        wallet_service_to_use = wallet_service or WalletServiceFactory.create_wallet_index_service(ctx)

        validator_storage_adapter = ValidatorStorageFactory.create_validator_storage(ctx.node_dirs)
        service = ValidatorIndexService(
            storage_adapter=validator_storage_adapter,
            user_index_service=user_service_to_use,
            wallet_index_service=wallet_service_to_use
        )

        return service


if __name__ == "__main__":
    from tests.test_config import dirs

    # Mock NodeContext for the factory's smoke test
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                user_service=UserServiceFactory.create_user_index_service(dirs),
                wallet_service=WalletServiceFactory.create_wallet_index_service(dirs),
                node_dirs=dirs
            )

    mock_node_context = MockNodeContext(dirs)

    # Test default behavior
    print("--- Testing factory default behavior ---")
    validator_service_default = ValidatorServiceFactory.create_validator_index_service(mock_node_context)
    print(f"✅ {validator_service_default} created successfully.")

    # Test with injected services
    print("\n--- Testing factory with injected services ---")
    authoritative_user_service = UserServiceFactory.create_user_index_service(mock_node_context)
    authoritative_wallet_service = WalletServiceFactory.create_wallet_index_service(mock_node_context)
    validator_service_injected = ValidatorServiceFactory.create_validator_index_service(
        mock_node_context,
        user_service=authoritative_user_service,
        wallet_service=authoritative_wallet_service
    )
    assert validator_service_injected.user_index_service is authoritative_user_service
    assert validator_service_injected.wallet_index_service is authoritative_wallet_service
    print("✅ Factory correctly used injected service instances.")

    print("\n--- Smoke Test Passed ---")
