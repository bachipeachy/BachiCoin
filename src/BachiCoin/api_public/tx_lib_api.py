#!/usr/bin/env python3
"""Transaction Public API - Single interface to all transaction operations."""

from typing import Dict, Any, List, Optional

# Local application imports
from BachiCoin.lib_transaction.tx_index_service import TxIndexService
from BachiCoin.lib_transaction.tx_service_factory import TxServiceFactory
from BachiCoin.lib_crossmodule.node_context import NodeContext, adapt_context_arg
from BachiCoin.lib_transaction.tx_config import TxType as _TxType, TxConfig as _TxConfig
from BachiCoin.lib_transaction.tx_signer import create_canonical_tx_hash as _create_canonical_tx_hash

TxType = _TxType
TxConfig = _TxConfig
create_canonical_tx_hash = _create_canonical_tx_hash


def create_tx_index_service(*args, **kwargs) -> TxIndexService:
    """
    Creates and initializes a fully configured TxIndexService by delegating.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(TxServiceFactory.create_tx_index_service, *args, **kwargs)

# =================== CORE API FUNCTIONS ===================

def create_tx_with_index(
        service: TxIndexService,
        tx_data: Dict[str, Any],
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        calculated_nonce: Optional[int] = None,
        override_nonce: Optional[int] = None,
) -> Dict[str, Any]:
    """Prepares a transaction object with defaults and JIT fields, but does not sign or save it."""
    return service.create_tx_with_index(
        tx_data=tx_data, 
        from_address=from_address, 
        to_address=to_address, 
        calculated_nonce=calculated_nonce, 
        override_nonce=override_nonce
    )

def save_signed_transaction(service: TxIndexService, signed_tx: Dict[str, Any]) -> bool:
    """Validates, saves, and indexes a signed transaction."""
    return service.save_signed_transaction(signed_tx)

def update_transaction(service: TxIndexService, tx_hash: str, update_data: Dict[str, Any]) -> bool:
    """Updates a full transaction record and its corresponding index entry."""
    return service.update_transaction(tx_hash, update_data)

def get_transaction(service: TxIndexService, tx_hash: str) -> Optional[Dict[str, Any]]:
    """Get a single transaction by hash."""
    return service.get_transaction(tx_hash)

def list_transactions(
        service: TxIndexService,
        tx_type: Optional[str] = None,
        currency: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return all transactions with index view, with optional filters."""
    return service.list_transactions(tx_type, currency, from_address, to_address)

def search_transactions(service: TxIndexService, query: str) -> List[Dict[str, Any]]:
    """Search transactions by a text query across multiple fields."""
    return service.search_transactions(query)

def delete_transaction(service: TxIndexService, tx_hash: str) -> bool:
    """Delete a transaction from storage and index atomically."""
    return service.delete_transaction(tx_hash)

# =================== ANALYTICS & REPORTING API ===================

def get_tx_index_stats(service: TxIndexService) -> Dict[str, Any]:
    """Get comprehensive transaction statistics from the index."""
    return service.get_tx_index_stats()

def get_transactions_by_address(service: TxIndexService, address: str) -> Dict[str, Any]:
    """Get all transactions where the address is a sender or receiver."""
    return service.get_transactions_by_address(address)

# =================== UTILITY API ===================

def sort_transactions_by_timestamp(
        service: TxIndexService, txs: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
    """Sort a list of transactions by timestamp."""
    return service.sort_transactions_by_timestamp(txs, reverse)

def rebuild_tx_index(service: TxIndexService) -> Dict[str, Any]:
    """Rebuild the entire index from all stored transaction JSON files."""
    return service.rebuild_index_from_records()

# =============================================================================
# WRAPPERS for tx_submittal.py
# =============================================================================
from BachiCoin.lib_transaction.tx_submittal import create_signed_tx as _create_signed_tx
from BachiCoin.lib_transaction.tx_submittal import submit_txs_for_user as _submit_txs_for_user

def create_signed_tx(node_context: NodeContext, tx_template: Dict[str, Any], global_address_book: Dict[str, str], nonce: int = None) -> Dict[str, Any]:
    """Public API wrapper for the create_signed_tx component."""
    return _create_signed_tx(node_context, tx_template, global_address_book, nonce)

async def submit_txs_for_user(node_context: NodeContext, user_name: str, user_tx_templates: list, global_address_book: Dict[str, str], pvt_key_map: Dict[str, str]) -> int:
    """Public API wrapper for the submit_txs_for_user component."""
    return await _submit_txs_for_user(node_context, user_name, user_tx_templates, global_address_book, pvt_key_map)
