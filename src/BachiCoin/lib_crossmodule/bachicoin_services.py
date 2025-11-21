#!/usr/bin/env python3
"""
bachicoin_services.py - Centralized function for initializing all services within a NodeContext.
"""

from BachiCoin.lib_crossmodule.node_context import NodeContext
from BachiCoin.lib_user.user_service_factory import UserServiceFactory
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
from BachiCoin.lib_blockchain.blockchain_service_factory import BlockchainServiceFactory
from BachiCoin.lib_mempool.mempool_service_factory import MempoolServiceFactory
from BachiCoin.lib_validator.validator_service_factory import ValidatorServiceFactory
from BachiCoin.lib_proposer.proposer_service_factory import ProposerServiceFactory
from BachiCoin.lib_attestor.attestor_service_factory import AttestorServiceFactory
from BachiCoin.lib_finalizer.finalizer_service_factory import FinalizerServiceFactory


def initialize_node_context_services(node_context: NodeContext) -> None:
    """
    Initializes all core services (blockchain, user, wallet, tx, mempool, validator,
    proposer, attestor, finalizer) for a given NodeContext.

    Args:
        node_context: The NodeContext object whose services need to be initialized.
    """
    if not node_context.node_dirs:
        raise ValueError("NodeContext must have 'node_dirs' set to initialize services.")

    node_context.blockchain_service = BlockchainServiceFactory.create_blockchain_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: blockchain_service ID: {id(node_context.blockchain_service)}")
    
    node_context.user_service = UserServiceFactory.create_user_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: user_service ID: {id(node_context.user_service)}")
    
    node_context.wallet_service = WalletServiceFactory.create_wallet_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: wallet_service ID: {id(node_context.wallet_service)}")
    
    node_context.tx_service = TxServiceFactory.create_tx_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: tx_service ID: {id(node_context.tx_service)}")
    
    node_context.mempool_service = MempoolServiceFactory.create_mempool_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: mempool_service ID: {id(node_context.mempool_service)}")
    
    node_context.validator_service = ValidatorServiceFactory.create_validator_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: validator_service ID: {id(node_context.validator_service)}")
    
    node_context.proposer_service = ProposerServiceFactory.create_proposer_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: proposer_service ID: {id(node_context.proposer_service)}")
    
    node_context.attestor_service = AttestorServiceFactory.create_attestor_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: attestor_service ID: {id(node_context.attestor_service)}")
    
    node_context.finalizer_service = FinalizerServiceFactory.create_finalizer_index_service(node_context)
    print(f"  [DEBUG] Node {node_context.node_dirs.base.name}: finalizer_service ID: {id(node_context.finalizer_service)}")


if __name__ == "__main__":
    from tests.test_config import dirs
    import logging

    logging.basicConfig(level=logging.INFO, format='%(message)s')
    log = logging.getLogger()

    print("\n🔹 Running smoke test for bachicoin_services.py...")

    # Create a dummy NodeContext
    test_node_context = NodeContext(node_dirs=dirs)
    print(f"  -> Created dummy NodeContext with node_dirs: {test_node_context.node_dirs.base}")

    # Ensure services are initially None
    assert test_node_context.user_service is None
    assert test_node_context.wallet_service is None
    assert test_node_context.blockchain_service is None
    # ... (add more assertions for other services if desired)

    # Initialize services
    initialize_node_context_services(test_node_context)
    print("  -> Services initialized.")

    # Verify services are no longer None
    assert test_node_context.user_service is not None
    assert test_node_context.wallet_service is not None
    assert test_node_context.blockchain_service is not None
    # ... (add more assertions for other services)

    # Basic check for a service function
    try:
        users = test_node_context.user_service.list_users()
        print(f"  -> Found {len(users)} users via initialized user_service.")
    except Exception as e:
        log.error(f"  💥 Error listing users: {e}")
        assert False, "Failed to list users after initialization."

    # Close services
    try:
        from BachiCoin.lib_postprocess.postprocess_state import close_services
        close_services({0: test_node_context}) # Pass as dict for close_services
        print("  -> Services closed.")
    except Exception as e:
        log.warning(f"  ⚠️  Error closing services: {e}")

    print("\n✅ bachicoin_services.py smoke test passed.")
