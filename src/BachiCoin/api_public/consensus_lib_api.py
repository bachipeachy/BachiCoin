#!/usr/bin/env python3
"""Public API for the Consensus Service (function-based)."""

from typing import Generator, Dict, Any, Union, List
from BachiCoin.lib_consensus.consensus import run_consensus
from BachiCoin.api_public.blockchain_lib_api import create_blockchain_index_service
from BachiCoin.api_public.validator_lib_api import create_validator_index_service
from BachiCoin.api_public.proposer_lib_api import create_proposer_index_service
from BachiCoin.api_public.attestor_lib_api import create_attestor_index_service
from BachiCoin.api_public.finalizer_lib_api import create_finalizer_index_service
from BachiCoin.api_public.mempool_lib_api import create_mempool_index_service
from BachiCoin.lib_consensus.consensus_join import drive_consensus_on_all_nodes as _drive_consensus_on_all_nodes

from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context
from BachiCoin.api_public.dirs_api import Dirs


def consensus_context(ctx_or_dirs: Union[NodeContext, Dirs, Any]) -> dict:
    """
    Factory to create all services required for consensus.
    Returns a dict of services to keep things simple and explicit.
    Accepts either a Dirs object or a NodeContext object.
    """
    ctx = adapt_context(ctx_or_dirs)
    services = {
        "blockchain_service": create_blockchain_index_service(ctx),
        "validator_service": create_validator_index_service(ctx),
        "proposer_service": create_proposer_index_service(ctx),
        "attestor_service": create_attestor_index_service(ctx),
        "finalizer_service": create_finalizer_index_service(ctx),
        "mempool_service": create_mempool_index_service(ctx),
    }
    required_keys = list(services.keys())
    for key in required_keys:
        assert key in services, f"Consensus context is missing required service: {key}"
    return services


def drive_consensus(
    node_context: NodeContext,
    slots_to_run: int
) -> Generator[Dict[str, Any], None, None]:
    """
    Public wrapper for the run_consensus generator.
    Expects a NodeContext object.
    """
    return run_consensus(
        node_context=node_context,
        slots_to_run=slots_to_run,
    )

async def drive_consensus_on_all_nodes(
    all_node_contexts: List[NodeContext],
    slots_to_run_per_node: int
) -> Generator[Dict[str, Any], None, None]:
    """
    Public wrapper for the drive_consensus_on_all_nodes generator.
    """
    async for result in _drive_consensus_on_all_nodes(all_node_contexts, slots_to_run_per_node):
        yield result
