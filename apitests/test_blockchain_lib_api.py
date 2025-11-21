#!/usr/bin/env python3
"""
test_blockchain_lib_api.py - Integration tests for the public blockchain API.
"""

import sys
from pathlib import Path

# Add project root and src directory to the Python path to resolve imports
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

from BachiCoin.api_public import blockchain_lib_api as api
from tests.test_config import dirs

def test_blockchain_api_smoke():
    """
    A smoke test that exercises the primary read-only functions of the
    blockchain public API, ensuring they run without errors against real data.
    """
    print("=== Testing Blockchain Public API with Real Data ===")
    service = api.create_blockchain_index_service(dirs)
    print(f"✅ {service} with storage at {dirs.blockchain}")

    # Helper to get data from flat or nested block
    def get_block_field(block, field_name, default=None):
        return block.get("header", block).get(field_name, default)

    # Get current chain state
    print(f"\n=== Current Chain State ===")
    chain_height = api.get_chain_height(service)
    print(f"Chain height: {chain_height}")
    
    chain_tip = api.get_chain_tip(service)
    if chain_tip:
        print(f"Chain tip: Height {get_block_field(chain_tip, 'height')}, Hash {chain_tip['block_hash'][:16]}...")
    else:
        print("STOPPING test as there are no blocks to proceed further ..")
        # In a real pytest scenario, we might use pytest.skip or an assertion
        return

    finalized_block = api.get_finalized_block(service)
    if finalized_block:
        print(f"Finalized: Height {get_block_field(finalized_block, 'height')}, Hash {finalized_block['block_hash'][:16]}...")

    justified_block = api.get_justified_block(service)
    if justified_block:
        print(f"Justified: Height {get_block_field(justified_block, 'height')}, Hash {justified_block['block_hash'][:16]}...")

    safe_block = api.get_safe_block(service)
    if safe_block:
        print(f"Safe: Height {get_block_field(safe_block, 'height')}, Hash {safe_block['block_hash'][:16]}...")

    # Get index statistics
    print(f"\n=== Index Statistics ===")
    stats = api.get_index_statistics(service)
    print(f"Total blocks: {stats['total_blocks']}")
    print(f"By status: {stats['by_status']}")
    print(f"Height range: {stats['height_range']}")
    print(f"Gas used total: {stats['total_gas_used']:,}")
    print(f"Transactions total: {stats['total_transactions']:,}")

    # List recent blocks
    print(f"\n=== Recent Blocks (Last 5) ===")
    recent_blocks = api.list_blocks(service, limit=5, offset=max(0, stats['total_blocks'] - 5))
    for block in recent_blocks:
        tx_count = len(block.get("body", block).get("transactions", []))
        gas_used = get_block_field(block, 'gas_used', 0)
        print(f"Height {get_block_field(block, 'height')}: {block['block_hash'][:16]}... "
              f"({tx_count} txs, {gas_used:,} gas)")

    # Test individual block lookup
    if chain_tip:
        print(f"\n=== Individual Block Lookup ===")
        tip_hash = chain_tip['block_hash']
        block_detail = api.get_block(service, tip_hash)
        if block_detail:
            print(f"Tip block details:")
            print(f"  Height: {get_block_field(block_detail, 'height')}")
            print(f"  Timestamp: {get_block_field(block_detail, 'timestamp')}")
            print(f"  Parent: {get_block_field(block_detail, 'parent_hash', 'N/A')[:16]}...")
            print(f"  Transactions: {len(block_detail.get('body', block_detail).get('transactions', []))}")
            print(f"  Gas used: {get_block_field(block_detail, 'gas_used', 0):,}")

    # Close service
    service.close()
    print("✅ Service closed")

if __name__ == "__main__":
    # This allows the script to be run directly for manual testing.
    test_blockchain_api_smoke()
