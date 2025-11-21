#!/usr/bin/env python3
"""mempool_helper.py – Pure helpers for queue, validation, and state handling."""

import time
from typing import Dict, Any, List

from BachiCoin.lib_mempool.mempool_config import (
    MempoolConfig,
    MempoolStatus,
    MempoolMetrics,
    get_base_fee,
)


def create_queue_entry(tx_data: Dict[str, Any]) -> Dict[str, Any]:
    """Pure function: create queue entry with priority scoring."""
    now = time.time()
    current_base_fee = get_base_fee()
    entry = {
        **tx_data,
        "arrival_time": now,
        "status": MempoolStatus.PENDING.value,
        "priority_score": MempoolMetrics.calculate_priority_score(tx_data, current_base_fee),
    }
    entry.setdefault("submitted_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)))
    return entry


def validate_mempool_limits(tx_data: Dict[str, Any], queue: List[Dict[str, Any]]) -> None:
    """Pure validation of mempool size + min fee."""
    priority_fee = tx_data.get("max_priority_fee_per_gas", 0)
    if priority_fee < MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD:
        raise ValueError(
            f"Priority fee {priority_fee} below minimum {MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD}"
        )
    if len(queue) >= MempoolConfig.MAX_POOL_SIZE:
        raise ValueError("Mempool full")


def update_fee_statistics(fee_stats: Dict[str, List[float]], tx_data: Dict[str, Any]) -> Dict[str, List[float]]:
    """Pure update of fee stats, returns new dict."""
    new_stats = dict(fee_stats)
    max_fee = tx_data.get("max_fee_per_gas", 0)
    priority_fee = tx_data.get("max_priority_fee_per_gas", 0)

    new_stats.setdefault("max_fees", []).append(max_fee)
    new_stats.setdefault("priority_fees", []).append(priority_fee)

    # Keep only last 100
    new_stats["max_fees"] = new_stats["max_fees"][-100:]
    new_stats["priority_fees"] = new_stats["priority_fees"][-100:]

    return new_stats


def get_current_pool_state(queue: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Pure view of pool state for validation."""
    account_pending = {}
    for tx in queue:
        addr = tx["from_address"]
        account_pending[addr] = account_pending.get(addr, 0) + 1

    return {
        "total_size": len(queue),
        "account_pending": account_pending,
        "memory_usage_bytes": len(str(queue).encode("utf-8")),
    }