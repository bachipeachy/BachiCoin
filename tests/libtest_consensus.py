#!/usr/bin/env python3
"""
libtest_consensus.py -- An integration test and usage example for the Consensus API.
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_config import dirs
from BachiCoin.api_public import (
    mempool_lib_api,
    validator_lib_api,
    proposer_lib_api,
    attestor_lib_api,
    finalizer_lib_api,
    blockchain_lib_api,
    consensus_lib_api,
    crossmodule_lib_api
)

class ConsensusApiTester:
    """A simple, sequential tester for the full consensus process."""

    def __init__(self):
        self.node_context = None

    async def run_all_tests(self):
        """Runs all test methods in a defined sequence."""
        print("=" * 60)
        print("== Running BachiCoin Consensus API Integration Test ==")
        print("=" * 60)

        self.test_01_initialize_services()
        await self.test_02_run_consensus_simulation()

        print("\n" + "=" * 60)
        print("✅✅✅ All Consensus API tests passed successfully! ✅✅✅")
        print("=" * 60)

    def test_01_initialize_services(self):
        """Initializes the full NodeContext with all required services."""
        print("\n--- 1. Initializing All Services in NodeContext ---")
        
        # Initialize NodeContext with the test directories
        self.node_context = crossmodule_lib_api.NodeContext(node_dirs=dirs)

        # Create and assign all necessary services to the context
        self.node_context.blockchain_service = blockchain_lib_api.create_blockchain_index_service(self.node_context)
        self.node_context.mempool_service = mempool_lib_api.create_mempool_index_service(self.node_context)
        self.node_context.validator_service = validator_lib_api.create_validator_index_service(self.node_context)
        self.node_context.proposer_service = proposer_lib_api.create_proposer_index_service(self.node_context)
        self.node_context.attestor_service = attestor_lib_api.create_attestor_index_service(self.node_context)
        self.node_context.finalizer_service = finalizer_lib_api.create_finalizer_index_service(self.node_context)
        
        print("✅ All services initialized and populated into NodeContext.")

    async def test_02_run_consensus_simulation(self):
        """Runs the main consensus simulation loop."""
        SLOTS_TO_RUN = 5 # Keep it short for a test run
        print(f"\n--- 2. Running Consensus Simulation for {SLOTS_TO_RUN} Slots ---")

        # The drive_consensus function now takes the populated NodeContext
        # and yields a summary for each slot processed.
        slot_iterator = consensus_lib_api.drive_consensus(self.node_context, slots_to_run=SLOTS_TO_RUN)
        
        processed_slots = 0
        for slot_summary in slot_iterator:
            block_hash_display = slot_summary.get('block_hash', 'N/A')
            if block_hash_display and block_hash_display != 'N/A':
                block_hash_display = block_hash_display[:16] + "..."

            print(f"  -> Slot {slot_summary['slot_processed']}: "
                  f"Block Hash: {block_hash_display}, "
                  f"Attestations: {slot_summary.get('attestations_submitted', 0)}")
            processed_slots += 1
        
        assert processed_slots == SLOTS_TO_RUN, \
            f"Expected to process {SLOTS_TO_RUN} slots, but only got summaries for {processed_slots}."
            
        print(f"\n✅ Consensus simulation completed for {processed_slots} slots.")


if __name__ == "__main__":
    tester = ConsensusApiTester()
    asyncio.run(tester.run_all_tests())
