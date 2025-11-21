#!/usr/bin/env python3
"""Transaction helpers – utilities for defaults, fee calc, JIT fields, and index handling."""

from datetime import datetime
from typing import Dict, Any
from BachiCoin.lib_transaction.tx_config import TxConfig, get_tx_defaults
from BachiCoin.lib_transaction.tx_validation import get_tx_schema_view


def apply_tx_defaults(tx_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge tx_data with system defaults and ensure required timestamps/fields are populated.
    Crucially, it preserves explicit None values for from_address and to_address.
    """
    defaults = get_tx_defaults()
    
    # Create a copy of defaults to modify, then merge tx_data
    merged = defaults.copy()
    
    for key, value in tx_data.items():
        # If tx_data explicitly provides None for from_address or to_address, preserve it.
        # Otherwise, merge the value from tx_data, potentially overwriting the default "".
        if key in ["from_address", "to_address"] and value is None:
            merged[key] = None
        else:
            merged[key] = value

    now = datetime.now().isoformat() + "Z"

    # Ensure critical fields exist and are not None
    for field in ["created_at", "last_modified", "timestamp"]:
        if not merged.get(field):  # catches None, "", 0
            merged[field] = now

    if not merged.get("status"):
        merged["status"] = "pending"

    # --- FIX: ensure fee/gas fields are never None ---
    if merged.get("max_fee_per_gas") is None:
        merged["max_fee_per_gas"] = TxConfig.FEE_DEFAULTS["standard"]["max_fee_per_gas"]

    if merged.get("max_priority_fee_per_gas") is None:
        merged["max_priority_fee_per_gas"] = TxConfig.FEE_DEFAULTS["standard"]["max_priority_fee_per_gas"]

    if merged.get("gas_limit") is None:
        merged["gas_limit"] = TxConfig.DEFAULT_GAS_LIMIT

    return merged


def populate_jit_fields(tx: Dict[str, Any], base_fee: float = 20.0) -> Dict[str, Any]:
    """Pure version: return new dict with JIT fee fields."""

    tx_copy = dict(tx)

    # Ensure required EIP-1559 fee fields
    tx_copy.setdefault("max_fee_per_gas", TxConfig.FEE_DEFAULTS["standard"]["max_fee_per_gas"])
    tx_copy.setdefault("max_priority_fee_per_gas", TxConfig.FEE_DEFAULTS["standard"]["max_priority_fee_per_gas"])

    gas_limit = tx_copy.get("gas_limit", TxConfig.DEFAULT_GAS_LIMIT)

    # Calculate effective fee metrics
    effective_gas_price = TxConfig.calculate_effective_gas_price(
        tx_copy["max_fee_per_gas"],
        tx_copy["max_priority_fee_per_gas"],
        base_fee,
    )
    total_fee = TxConfig.calculate_total_fee(gas_limit, effective_gas_price)

    # Inject JIT fields
    tx_copy.update({
        "base_fee_per_gas": base_fee,
        "effective_gas_price": effective_gas_price,
        "gas_used": gas_limit,
        "total_fee": total_fee,
        "confirmations": 0,
    })

    return tx_copy


def build_index_entry(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Build schema-compliant index entry from tx_data."""
    schema = get_tx_schema_view("index")
    # Ensure we get a default value if a field is missing from the tx dict
    defaults = get_tx_defaults()
    return {field: tx.get(field, defaults.get(field)) for field in schema}


def parse_iso8601(ts: str) -> float:
    """Parse ISO 8601 timestamp into UNIX epoch seconds (gracefully fallback)."""
    try:
        if ts.endswith("Z"):
            dt = datetime.fromisoformat(ts[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(ts)
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0
