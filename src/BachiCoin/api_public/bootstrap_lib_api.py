#!/usr/bin/env python3
"""Public API for the BachiCoin bootstrap module."""

from typing import Dict, Tuple, List, Any, Optional

# WRAPPERS for NodeContext
from BachiCoin.lib_crossmodule.node_context import NodeContext as _NodeContext
NodeContext = _NodeContext

# WRAPPERS for bootstrap_config.py
from BachiCoin.lib_bootstrap.bootstrap_config import (
    CURRENCY as _CURRENCY,
    GENESIS_MINT_AMOUNT as _GENESIS_MINT_AMOUNT,
    SYSTEM_USERS as _SYSTEM_USERS,
    GENESIS_VALIDATORS as _GENESIS_VALIDATORS,
    BOOTSTRAP_USERS as _BOOTSTRAP_USERS,
)
CURRENCY = _CURRENCY
GENESIS_MINT_AMOUNT = _GENESIS_MINT_AMOUNT
SYSTEM_USERS = _SYSTEM_USERS
GENESIS_VALIDATORS = _GENESIS_VALIDATORS
BOOTSTRAP_USERS = _BOOTSTRAP_USERS

# WRAPPERS for bootstrap_ledger.py
from BachiCoin.lib_bootstrap.bootstrap_ledger import bootstrap_ledger as _bootstrap_ledger

async def bootstrap_ledger(node_context: NodeContext) -> str:
    """Bootstraps the ledger by creating and submitting the genesis mint transaction."""
    return await _bootstrap_ledger(node_context)

# WRAPPERS for bootstrap_utils.py
from BachiCoin.lib_bootstrap.bootstrap_utils import (
    get_maps_for_user_identities as _get_maps_for_user_identities,
    create_and_map_users_and_wallets as _create_and_map_users_and_wallets,
    bootstrap_register_validators as _bootstrap_register_validators,
)

def get_maps_for_user_identities(node_context: NodeContext) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Scans all users known to a node_context, regenerates their keys and addresses
    in-memory, and returns a tuple of (address_map, private_key_map).
    """
    return _get_maps_for_user_identities(node_context)

async def create_and_map_users_and_wallets(
    node_context: NodeContext,
    user_profiles: List[Dict[str, Any]],
    passphrase_seed: Optional[str] = None
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Creates users and their wallets if they don't already exist, and returns
    comprehensive address and private key maps for all specified users.
    """
    return await _create_and_map_users_and_wallets(node_context, user_profiles, passphrase_seed)

def bootstrap_register_validators(node_context: NodeContext, users_on_node: List[Dict[str, Any]], full_address_map: Dict[str, str]):
    """
    Registers users with 'validator' user_type as validators during the bootstrap process.
    """
    _bootstrap_register_validators(node_context, users_on_node, full_address_map)

# WRAPPERS for global_address_book.py
from BachiCoin.lib_bootstrap.global_address_book import GlobalAddressBook as _GlobalAddressBook

class GlobalAddressBook(_GlobalAddressBook):
    """A file-based, flat address book mapping user keys to public addresses."""
    pass

# WRAPPERS for bootstrap_singlenode.py
from BachiCoin.lib_bootstrap.bootstrap_singlenode import bootstrap_singlenode as _bootstrap_singlenode
from BachiCoin.lib_crossmodule.dirs import Dirs

async def bootstrap_singlenode(
        node_id: int,
        port: int,
        node_dirs: Dirs,
        network_adapter: str = "loopback",
) -> NodeContext:
    """Sequentially initialize and bootstrap a single node. """
    return await _bootstrap_singlenode(node_id, port, node_dirs, network_adapter)
