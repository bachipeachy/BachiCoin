#!/usr/bin/env python3
"""
blockchain_helper.py

Pure helper utilities used by BlockchainIndexService.
- apply_block_defaults: merge defaults and provided data
- populate_jit_block_fields: compute JIT / derived fields (gas_used, roots, totals)
- build_index_entry_from_block: create an index entry dict from a block
- get_default_for_index_field: utility for missing field defaults
"""

from typing import Dict, Any, List
import time
from datetime import datetime

from BachiCoin.lib_blockchain.blockchain_config import (
    get_block_full_defaults,
    get_block_schema_view,
    get_block_defaults_for_view,
    calculate_gas_used,
    calculate_total_fees,
    generate_block_hash,
)
from BachiCoin.lib_blockchain.blockchain_validation import assert_valid_creation_data
from BachiCoin.lib_blockchain.blockchain_config import BlockStatus
from BachiCoin.lib_blockchain.blockchain_merkle_verkle import calculate_txs_root


def serialize_block_for_json(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert block data to JSON-serializable format, aware of header/body."""
    import copy
    serializable = copy.deepcopy(block_data)

    # Handle bytes in the header (for regular blocks)
    if "header" in serializable and isinstance(serializable.get("header"), dict):
        if "extra_data" in serializable["header"] and isinstance(serializable["header"]["extra_data"], bytes):
            serializable["header"]["extra_data"] = serializable["header"]["extra_data"].hex()
            
    # Handle bytes at the top level (for genesis block)
    if "extra_data" in serializable and isinstance(serializable["extra_data"], bytes):
        serializable["extra_data"] = serializable["extra_data"].hex()
            
    return serializable


def apply_block_defaults(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge supplied block_data with full defaults and ensure required timestamp keys exist.
    This returns a *mutable* dict ready for JIT population.
    """
    defaults = get_block_full_defaults()
    merged = {**defaults, **(block_data or {})}
    
    # Handle both flat and nested structures
    header = merged.get("header", merged) # Use self if no header
    
    if header.get("timestamp") is None:
        header["timestamp"] = int(time.time())
        
    # If we modified 'merged' directly, put it back if there was a header
    if "header" in merged:
        merged["header"] = header
    
    now_iso = datetime.now().isoformat() + "Z"
    merged.setdefault("created_at", now_iso)
    merged.setdefault("last_modified", now_iso)
        
    return merged


def populate_jit_block_fields(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Populate JIT (just-in-time) derived fields for a block, aware of header/body structure.
    """
    is_nested = "header" in block_data
    
    header = block_data.get("header", block_data) # Use self if flat
    body = block_data.get("body", block_data)     # Use self if flat
    
    transactions: List[Dict[str, Any]] = body.get("transactions") or []
    
    # Populate fields in their correct locations
    if is_nested:
        block_data["transaction_count"] = len(transactions)
    else: # Flat structure
        block_data["transaction_count"] = len(transactions)

    header["gas_used"] = calculate_gas_used(transactions)
    
    txs_root = header.get("transactions_root")
    if (not txs_root or txs_root == "0x" + "0" * 64) and transactions:
        header["transactions_root"] = calculate_txs_root(transactions)

    header.setdefault("state_root", "0x" + "0" * 64)
    header.setdefault("receipts_root", "0x" + "0" * 64)
    header.setdefault("transactions_root", header.get("transactions_root") or "0x" + "0" * 64)

    block_data["total_fees"] = calculate_total_fees(transactions)
    
    now_iso = datetime.now().isoformat() + "Z"
    block_data.setdefault("received_at", now_iso)
    block_data.setdefault("validated_at", now_iso)

    if is_nested:
        block_data["header"] = header
        block_data["body"] = body

    block_data["block_hash"] = generate_block_hash(header)

    return block_data


def prepare_block_for_storage_and_index(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    High-level helper that:
      - applies defaults
      - populates JIT fields
      - validates creation semantic correctness (calls assert_valid_creation_data)
      - returns both the canonical (possibly non-serializable) block dict and the serializable dict

    Returns a dictionary with keys:
      - 'block': the validated block (with JIT fields and block_hash)
      - 'serializable': block serialized for JSON storage (serialize_block_for_json)
    """
    blk = apply_block_defaults(block_data)
    blk = populate_jit_block_fields(blk)

    # Validation is part of the creation pipeline
    assert_valid_creation_data(blk)

    serializable = serialize_block_for_json(blk)
    return {"block": blk, "serializable": serializable}


def build_index_entry_from_block(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the index entry mapping for a block from the full block record,
    aware of the header/body structure.
    """
    schema = get_block_schema_view("index")
    entry: Dict[str, Any] = {}
    header = block_data.get("header", {})
    body = block_data.get("body", {})

    for field in schema.keys():
        if field == "block_hash":
            continue
        
        # Get value from the correct location
        if field in header:
            value = header.get(field)
        elif field in body:
            value = body.get(field)
        else:
            value = block_data.get(field)

        if field == "extra_data" and isinstance(value, (bytes, bytearray)):
            value = value.hex() if value else ""
            
        entry[field] = value if value is not None else get_block_defaults_for_view("index").get(field, "")

    # computed convenience fields
    entry["transaction_count"] = len(body.get("transactions", []))
    entry["gas_used"] = header.get("gas_used", 0)
    entry["status"] = block_data.get("status", BlockStatus.PROPOSED.value)
    entry["is_canonical"] = block_data.get("is_canonical", False)

    return entry


def get_default_for_index_field(field: str) -> Any:
    """
    Utility: return default value for an index field using config defaults.
    """
    defaults = get_block_defaults_for_view("index")
    return defaults.get(field, "")
