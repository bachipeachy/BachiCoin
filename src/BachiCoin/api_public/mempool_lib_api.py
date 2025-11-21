#!/usr/bin/env python3
"""Mempool Public API - Single, stateful interface for all mempool operations."""

from typing import Dict, Any, List, Optional

from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_mempool.mempool_service_factory import MempoolServiceFactory
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg

# =================== FACTORY FUNCTION ===================

def create_mempool_index_service(*args, **kwargs):
    """Create a mempool index service with automatic context normalization."""
    return adapt_context_arg(MempoolServiceFactory.create_mempool_index_service, *args, **kwargs)

# =================== PUBLIC API WRAPPERS ===================

async def submit_transaction(
service: MempoolIndexService, tx_data: Dict[str, Any]
) -> str:
    """Validates and submits a transaction to the mempool."""
    return await service.submit_tx(tx_data)

def get_mempool_status(
        service: MempoolIndexService
) -> Dict[str, Any]:
    """Retrieves the current status and statistics of the mempool."""
    return service.get_mempool_status()

def get_pending_transactions(
        service: MempoolIndexService, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Gets a list of pending transactions, sorted by priority."""
    return service.get_pending_transactions(limit)

def cleanup_expired(
        service: MempoolIndexService
) -> Dict[str, int]:
    """Removes expired transactions from the mempool."""
    return service.cleanup_expired()

def get_account_transactions(
        service: MempoolIndexService, from_address: str
) -> List[Dict[str, Any]]:
    """Gets all mempool transactions for a specific account."""
    return service.get_account_transactions(from_address)

def remove_transaction(
        service: MempoolIndexService, tx_hash: str
) -> bool:
    """Removes a specific transaction from the mempool by its hash."""
    return service.remove_transaction(tx_hash)


if __name__ == "__main__":
    # !/usr/bin/env python3
    """Smoke test for Mempool Public API using a full mock NodeContext."""

    import asyncio
    import json
    import random
    from pathlib import Path
    from typing import Dict, Any

    from BachiCoin.api_public.mempool_lib_api import (
        create_mempool_index_service,
        submit_transaction,
        get_mempool_status,
    )
    from BachiCoin.lib_crossmodule.node_context import NodeContext
    from BachiCoin.api_public.user_lib_api import create_user_index_service
    from BachiCoin.api_public.wallet_lib_api import create_wallet_index_service
    from tests.test_config import dirs


    # -------------------- Mock Blockchain --------------------
    class MockBlockchainService:
        def get_nonce_and_balance(self, address: str) -> Dict[str, Any]:
            # Simulate account states
            if address.startswith("0xaaaa"):
                return {"nonce": 5, "balance": 100.0}
            elif address.startswith("0xbbbb"):
                return {"nonce": 10, "balance": 200.0}
            return {"nonce": 0, "balance": 0.0}


    # -------------------- Mock NodeContext --------------------
    class MockNodeContext(NodeContext):
        def __init__(self, dirs):
            super().__init__(
                user_service=create_user_index_service(dirs),
                wallet_service=create_wallet_index_service(dirs),
                blockchain_service=MockBlockchainService(),
                node_dirs=dirs,
                port=0,
                network="testnet",
                currency="BACHI"
            )


    mock_node_context = MockNodeContext(dirs)

    # -------------------- Load transactions --------------------
    tx_index_file = Path(dirs.tx) / "tx_index.json"
    assert tx_index_file.exists(), f"Transaction index file not found at {tx_index_file}"

    with open(tx_index_file, "r") as f:
        tx_records = json.load(f).get("txs", {})
    print(f"✅ Loaded {len(tx_records)} transaction records for submission.")


    # -------------------- Async test runner --------------------
    async def run_mempool_smoke():
        # Step 1: Create MempoolIndexService with full NodeContext
        mempool_service = create_mempool_index_service(node_context=mock_node_context)
        print(f"✅ Mempool service created with storage at {dirs.mempool}")

        # Step 2: Submit all transactions
        for tx_hash, tx_data in tx_records.items():
            tx_copy = dict(tx_data)

            # Ensure required fields
            tx_copy.setdefault("gas_limit", 21000)
            tx_copy.setdefault("tx_hash", tx_hash)

            # Assign mock from_address
            if tx_copy.get("from_address") and tx_copy["from_address"].startswith("0x"):
                tx_copy["from_address"] = random.choice([
                    "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                ])

            try:
                returned_hash = await submit_transaction(mempool_service, tx_copy)
                print(f"  -> Submitted tx {returned_hash[:10]}...")
            except ValueError as e:
                print(f"  -> ❌ Failed to submit tx {tx_hash[:10]}...: {e}")

        # Step 3: Check mempool status
        status = get_mempool_status(mempool_service)
        print(f"✅ Total transactions in mempool: {status['total_transactions']}")
        assert status['total_transactions'] == len(tx_records), "Mismatch in expected mempool size"

        print("\n--- ✅ Mempool Public API Smoke Test Passed! ---")


    # -------------------- Run test --------------------
    if __name__ == "__main__":
        asyncio.run(run_mempool_smoke())