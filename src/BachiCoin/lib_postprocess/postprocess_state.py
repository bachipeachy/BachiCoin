#!/usr/bin/env python3
"""
postprocess_state.py - A pure, stateless library for calculating state transitions.
Drop-in replacement implementing Decimal arithmetic and robust balance updates.

Notes:
- Assumes block body contains ordered 'transactions' to be applied sequentially.
- Uses COMPUTATIONAL_DECIMAL_PLACES to quantize all monetary operations.
- Keeps existing public API contract and function names.
"""

import logging
from typing import Dict, Set, List, Any, TypedDict, Tuple
from decimal import Decimal, getcontext, ROUND_DOWN

from BachiCoin.lib_postprocess.postprocess_config import COMPUTATIONAL_DECIMAL_PLACES
from BachiCoin.lib_nonce.nonce import increment_nonce
from BachiCoin.lib_transaction.tx_config import TxType
from BachiCoin.lib_crossmodule.node_context import NodeContext

# Configure Decimal context precision reasonably high to avoid intermediate loss
getcontext().prec = 28

# Helpers for Decimal quantization
_QUANT = Decimal("1." + ("0" * COMPUTATIONAL_DECIMAL_PLACES)) if COMPUTATIONAL_DECIMAL_PLACES > 0 else Decimal("1")


class BalanceChange(TypedDict):
    wallet_id: str
    wallet_name: str
    change: float
    new_balance: float


class UpdateResult(TypedDict):
    block_hash: str
    processed_tx_count: int
    skipped_tx_count: int
    affected_user_ids: Set[str]
    balance_changes: List[BalanceChange]
    errors: List[str]


# -------------------------
# Internal helpers
# -------------------------

def _to_decimal(value: Any) -> Decimal:
    """Convert numeric-ish value to Decimal and quantize to computation places."""
    if value is None:
        return Decimal("0").quantize(_QUANT)
    if isinstance(value, Decimal):
        return value.quantize(_QUANT)
    try:
        return Decimal(str(value)).quantize(_QUANT)
    except Exception:
        # Fallback: treat as zero on bad input to avoid crash (shouldn't happen)
        return Decimal("0").quantize(_QUANT)


def _dec_to_float(v: Decimal) -> float:
    """Convert Decimal to float for backward service compatibility."""
    return float(v.quantize(_QUANT))


# Balance ops using service API (which expects floats): keep Decimal internally, pass floats out.
def _apply_debit(node_ctx: NodeContext, wallet_id: str, debit_amount: Decimal) -> Decimal:
    """Debit a wallet by debit_amount (Decimal). Returns new balance (Decimal).
       Raises ValueError if insufficient funds.
    """
    wallet = node_ctx.wallet_service.get_wallet(wallet_id)
    if not wallet:
        raise ValueError(f"Wallet '{wallet_id}' not found for debit.")
    current = _to_decimal(wallet.get("balance", 0.0))
    new = (current - debit_amount).quantize(_QUANT)
    if new < Decimal("0"):
        raise ValueError(f"Insufficient balance in wallet '{wallet.get('name')}' ({wallet_id}): needs {debit_amount}, has {current}")
    # update via wallet_service using float for existing code compatibility
    ok = node_ctx.wallet_service.update_account_state(wallet_id, balance=_dec_to_float(new))
    if not ok:
        raise ValueError(f"Failed to update wallet '{wallet_id}' during debit.")
    return new


def _apply_credit(node_ctx: NodeContext, wallet_id: str, credit_amount: Decimal) -> Decimal:
    """Credit a wallet by credit_amount (Decimal). Returns new balance (Decimal)."""
    wallet = node_ctx.wallet_service.get_wallet(wallet_id)
    if not wallet:
        raise ValueError(f"Wallet '{wallet_id}' not found for credit.")
    current = _to_decimal(wallet.get("balance", 0.0))
    new = (current + credit_amount).quantize(_QUANT)
    ok = node_ctx.wallet_service.update_account_state(wallet_id, balance=_dec_to_float(new))
    if not ok:
        raise ValueError(f"Failed to update wallet '{wallet_id}' during credit.")
    return new


# -------------------------
# Core engine
# -------------------------

def _update_tx_records(
        all_node_contexts: Dict[int, NodeContext],
        block: Dict[str, Any]
) -> None:
    """Mark transactions as confirmed after successful state application."""
    any_node_context = next(iter(all_node_contexts.values()))
    tx_service = any_node_context.tx_service
    transactions = block.get("body", {}).get("transactions", [])
    block_hash = block.get("block_hash")
    block_height = block.get("header", block).get("height", -1)

    for tx in transactions:
        tx_service.update_transaction(tx.get("tx_hash"), update_data={
            "block_number": block_height,
            "block_hash": block_hash,
            "status": "confirmed"
        })


def _apply_block_balance_changes(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block: Dict[str, Any]
) -> Tuple[Set[str], List[BalanceChange], List[str], int]:
    """
    Applies transactions in a block (ordered) to wallet balances.
    Returns (affected_user_ids, balance_changes, errors, processed_count).
    """

    transactions = block.get("body", {}).get("transactions", [])
    users_to_reconcile: Dict[str, NodeContext] = {}
    balance_changes: List[BalanceChange] = []
    errors: List[str] = []
    sender_tx_counts: Dict[str, int] = {}
    processed_count = 0

    any_tx_service = next(iter(all_node_contexts.values())).tx_service

    # Helper: find node context + wallet id for an address
    def _get_context_for_address(addr: str) -> Tuple[NodeContext, str]:
        node_id = address_to_node_map.get(addr)
        if node_id is None:
            raise ValueError(f"Address {addr} not found in provided address-to-node map.")
        node_ctx = all_node_contexts.get(node_id)
        if node_ctx is None:
            raise ValueError(f"Node context for node ID {node_id} not found.")
        wallet_id = node_ctx.wallet_service.get_wallet_id_by_address(addr)
        if wallet_id is None:
            raise ValueError(f"Wallet ID for address {addr} not found on its home node {node_id}.")
        return node_ctx, wallet_id

    # We assume system wallets (pool, burn) are on node 0
    node0 = all_node_contexts[0]
    users_list = node0.user_service.list_users()
    ledger_system_user = next((u for u in users_list if f"{u.get('first_name')} {u.get('last_name')}" == "Ledger System"), None)

    burn_wallet_id = None
    pool_wallet_id = None
    if ledger_system_user:
        ledger_wallets = node0.wallet_service.list_wallets_by_user(ledger_system_user['user_id'])
        burn_w = next((w for w in ledger_wallets if w['wallet_type'] == 'burn'), None)
        pool_w = next((w for w in ledger_wallets if w['wallet_type'] == 'pool'), None)
        if burn_w:
            burn_wallet_id = burn_w['wallet_id']
        if pool_w:
            pool_wallet_id = pool_w['wallet_id']

    # Iterate transactions in given block order
    for tx in transactions:
        tx_hash = tx.get("tx_hash")
        try:
            existing_tx = any_tx_service.get_transaction(tx_hash)
            if existing_tx and existing_tx.get("status") == "confirmed":
                logging.info(f"Skipping already-confirmed tx {tx_hash[:10]}")
                continue

            tx_type = tx.get("tx_type")
            from_addr = tx.get("from_address")
            to_addr = tx.get("to_address")
            amount = _to_decimal(tx.get("amount", 0.0))
            gas_fee = _to_decimal(tx.get("total_fee", 0.0))

            processed_count += 1

            # Small helper to credit the pool with gas (if present)
            def _credit_pool_with_gas(fee: Decimal):
                if fee > Decimal("0") and pool_wallet_id:
                    new_pool = _apply_credit(node0, pool_wallet_id, fee)
                    users_to_reconcile[node0.wallet_service.get_wallet(pool_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": pool_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(pool_wallet_id)["name"],
                        "change": _dec_to_float(fee),
                        "new_balance": _dec_to_float(new_pool)
                    })

            if tx_type == TxType.MINT.value:
                # Credit receiver from "nowhere" (mint tx creates money).
                to_ctx, to_wid = _get_context_for_address(to_addr)
                new_bal = _apply_credit(to_ctx, to_wid, amount)
                users_to_reconcile[to_ctx.wallet_service.get_wallet(to_wid)["user_id"]] = to_ctx
                balance_changes.append({
                    "wallet_id": to_wid,
                    "wallet_name": to_ctx.wallet_service.get_wallet(to_wid)["name"],
                    "change": _dec_to_float(amount),
                    "new_balance": _dec_to_float(new_bal)
                })

            elif tx_type == TxType.REWARD.value:
                # Credit user, debit pool
                to_ctx, to_wid = _get_context_for_address(to_addr)
                new_to = _apply_credit(to_ctx, to_wid, amount)
                users_to_reconcile[to_ctx.wallet_service.get_wallet(to_wid)["user_id"]] = to_ctx
                balance_changes.append({
                    "wallet_id": to_wid,
                    "wallet_name": to_ctx.wallet_service.get_wallet(to_wid)["name"],
                    "change": _dec_to_float(amount),
                    "new_balance": _dec_to_float(new_to)
                })
                if pool_wallet_id:
                    new_pool = _apply_debit_for_pool(node0, pool_wallet_id, amount)
                    users_to_reconcile[node0.wallet_service.get_wallet(pool_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": pool_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(pool_wallet_id)["name"],
                        "change": -_dec_to_float(amount),
                        "new_balance": _dec_to_float(new_pool)
                    })

            elif tx_type == TxType.TRANSFER.value:
                # Debit sender (amount + gas_fee), credit receiver (amount), credit pool with gas_fee
                from_ctx, from_wid = _get_context_for_address(from_addr)
                debit_amt = (amount + gas_fee).quantize(_QUANT)
                new_from = _apply_debit(from_ctx, from_wid, debit_amt)
                sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
                users_to_reconcile[from_ctx.wallet_service.get_wallet(from_wid)["user_id"]] = from_ctx
                balance_changes.append({
                    "wallet_id": from_wid,
                    "wallet_name": from_ctx.wallet_service.get_wallet(from_wid)["name"],
                    "change": -_dec_to_float(debit_amt),
                    "new_balance": _dec_to_float(new_from)
                })

                to_ctx, to_wid = _get_context_for_address(to_addr)
                new_to = _apply_credit(to_ctx, to_wid, amount)
                users_to_reconcile[to_ctx.wallet_service.get_wallet(to_wid)["user_id"]] = to_ctx
                balance_changes.append({
                    "wallet_id": to_wid,
                    "wallet_name": to_ctx.wallet_service.get_wallet(to_wid)["name"],
                    "change": _dec_to_float(amount),
                    "new_balance": _dec_to_float(new_to)
                })

                _credit_pool_with_gas(gas_fee)

            elif tx_type == TxType.BURN.value:
                # Debit user (amount + gas_fee), credit burn wallet, credit pool with gas_fee
                from_ctx, from_wid = _get_context_for_address(from_addr)
                debit_amt = (amount + gas_fee).quantize(_QUANT)
                new_from = _apply_debit(from_ctx, from_wid, debit_amt)
                sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
                users_to_reconcile[from_ctx.wallet_service.get_wallet(from_wid)["user_id"]] = from_ctx
                balance_changes.append({
                    "wallet_id": from_wid,
                    "wallet_name": from_ctx.wallet_service.get_wallet(from_wid)["name"],
                    "change": -_dec_to_float(debit_amt),
                    "new_balance": _dec_to_float(new_from)
                })

                if burn_wallet_id:
                    new_burn = _apply_credit(node0, burn_wallet_id, amount)
                    users_to_reconcile[node0.wallet_service.get_wallet(burn_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": burn_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(burn_wallet_id)["name"],
                        "change": _dec_to_float(amount),
                        "new_balance": _dec_to_float(new_burn)
                    })
                _credit_pool_with_gas(gas_fee)

            elif tx_type == TxType.SLASH.value:
                from_ctx, from_wid = _get_context_for_address(from_addr)
                debit_amt = (amount + gas_fee).quantize(_QUANT)
                new_from = _apply_debit(from_ctx, from_wid, debit_amt)
                sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
                users_to_reconcile[from_ctx.wallet_service.get_wallet(from_wid)["user_id"]] = from_ctx
                balance_changes.append({
                    "wallet_id": from_wid,
                    "wallet_name": from_ctx.wallet_service.get_wallet(from_wid)["name"],
                    "change": -_dec_to_float(debit_amt),
                    "new_balance": _dec_to_float(new_from)
                })

                if pool_wallet_id:
                    pool_inc = (amount + gas_fee).quantize(_QUANT)
                    new_pool = _apply_credit(node0, pool_wallet_id, pool_inc)
                    users_to_reconcile[node0.wallet_service.get_wallet(pool_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": pool_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(pool_wallet_id)["name"],
                        "change": _dec_to_float(pool_inc),
                        "new_balance": _dec_to_float(new_pool)
                    })

            elif tx_type == TxType.STAKE.value:
                from_ctx, from_wid = _get_context_for_address(from_addr)
                debit_amt = (amount + gas_fee).quantize(_QUANT)
                new_from = _apply_debit(from_ctx, from_wid, debit_amt)
                sender_tx_counts[from_addr] = sender_tx_counts.get(from_addr, 0) + 1
                users_to_reconcile[from_ctx.wallet_service.get_wallet(from_wid)["user_id"]] = from_ctx
                balance_changes.append({
                    "wallet_id": from_wid,
                    "wallet_name": from_ctx.wallet_service.get_wallet(from_wid)["name"],
                    "change": -_dec_to_float(debit_amt),
                    "new_balance": _dec_to_float(new_from)
                })

                if pool_wallet_id:
                    pool_inc = (amount + gas_fee).quantize(_QUANT)
                    new_pool = _apply_credit(node0, pool_wallet_id, pool_inc)
                    users_to_reconcile[node0.wallet_service.get_wallet(pool_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": pool_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(pool_wallet_id)["name"],
                        "change": _dec_to_float(pool_inc),
                        "new_balance": _dec_to_float(new_pool)
                    })

            elif tx_type == TxType.UNSTAKE.value:
                # Debit pool, credit user
                if pool_wallet_id:
                    new_pool = _apply_debit(node0, pool_wallet_id, amount)
                    users_to_reconcile[node0.wallet_service.get_wallet(pool_wallet_id)["user_id"]] = node0
                    balance_changes.append({
                        "wallet_id": pool_wallet_id,
                        "wallet_name": node0.wallet_service.get_wallet(pool_wallet_id)["name"],
                        "change": -_dec_to_float(amount),
                        "new_balance": _dec_to_float(new_pool)
                    })
                to_ctx, to_wid = _get_context_for_address(to_addr)
                new_to = _apply_credit(to_ctx, to_wid, amount)
                users_to_reconcile[to_ctx.wallet_service.get_wallet(to_wid)["user_id"]] = to_ctx
                balance_changes.append({
                    "wallet_id": to_wid,
                    "wallet_name": to_ctx.wallet_service.get_wallet(to_wid)["name"],
                    "change": _dec_to_float(amount),
                    "new_balance": _dec_to_float(new_to)
                })

            else:
                processed_count -= 1
                errors.append(f"Tx {tx_hash[:10]}: Unknown tx_type '{tx_type}'.")
        except Exception as e:
            # Stop processing and bubble up as a hard failure (keeps previous semantics)
            raise ValueError(f"Failed processing tx {tx_hash}: {e}") from e

    # increment nonce for senders
    for addr, count in sender_tx_counts.items():
        node_ctx, _ = _get_context_for_address(addr)
        increment_nonce(addr, node_ctx.wallet_service, count)

    # reconcile user totals
    for user_id, node_ctx in users_to_reconcile.items():
        node_ctx.wallet_service.reconcile_user_balance(user_id)

    return set(users_to_reconcile.keys()), balance_changes, errors, processed_count


# A small helper used above to debit pool safely with consistent errors
def _apply_debit_for_pool(node_ctx: NodeContext, wallet_id: str, amount: Decimal) -> Decimal:
    return _apply_debit(node_ctx, wallet_id, amount.quantize(_QUANT))


# -------------------------
# Public API functions (unchanged signatures)
# -------------------------

def update_block_state(
        all_node_contexts: Dict[int, NodeContext],
        address_to_node_map: Dict[str, int],
        block_hash: str
) -> UpdateResult:
    any_node_context = next(iter(all_node_contexts.values()))
    block = any_node_context.blockchain_service.get_block(block_hash)

    if not block:
        return {
            "block_hash": block_hash, "processed_tx_count": 0, "skipped_tx_count": 0,
            "affected_user_ids": set(), "balance_changes": [], "errors": ["Block not found."]
        }

    if block.get("state_processed"):
        logging.warning(f"Block {block_hash[:10]} has already been processed. Skipping.")
        return {
            "block_hash": block_hash, "processed_tx_count": 0,
            "skipped_tx_count": len(block.get("body", {}).get("transactions", [])),
            "affected_user_ids": set(), "balance_changes": [], "errors": [f"Block {block_hash[:10]} already processed."]
        }

    affected_users, balance_changes, errors, processed_count = _apply_block_balance_changes(
        all_node_contexts, address_to_node_map, block
    )

    # Only update transaction records after balances are applied
    _update_tx_records(all_node_contexts, block)
    any_node_context.blockchain_service.update_block(block_hash, {"state_processed": True})
    logging.info(f"Successfully processed and marked block {block_hash[:10]} as state_processed=True.")

    total_tx_in_block = len(block.get("body", {}).get("transactions", []))
    skipped_count = total_tx_in_block - processed_count

    return {
        "block_hash": block_hash,
        "processed_tx_count": processed_count,
        "skipped_tx_count": skipped_count,
        "affected_user_ids": affected_users,
        "balance_changes": balance_changes,
        "errors": errors
    }


def get_ledger_balance(all_node_contexts: Dict[int, NodeContext]) -> float:
    """Sum balances across all wallets using Decimal then return float rounded to COMPUTATIONAL_DECIMAL_PLACES."""
    total = Decimal("0")
    for node_context in all_node_contexts.values():
        for w in node_context.wallet_service.list_wallets():
            total += _to_decimal(w.get("balance", 0.0))
    return _dec_to_float(total.quantize(_QUANT))


def get_ledger_summary(all_node_contexts: Dict[int, NodeContext]) -> Dict[str, Any]:
    total_wallets = 0
    total_users = 0
    for node_context in all_node_contexts.values():
        total_wallets += len(node_context.wallet_service.list_wallets())
        total_users += len(node_context.user_service.list_users())

    return {
        "total_balance": get_ledger_balance(all_node_contexts),
        "wallet_count": total_wallets,
        "user_count": total_users
    }


def get_user_balance(node_context: NodeContext, user_id: str) -> Dict[str, Any]:
    wallet_service = node_context.wallet_service
    user_wallets = [w for w in wallet_service.list_wallets() if w.get("user_id") == user_id]
    balance = Decimal("0")
    for w in user_wallets:
        balance += _to_decimal(w.get("balance", 0.0))
    user_data = node_context.user_service.get_user(user_id)
    return {
        "user_id": user_id,
        "name": f"{user_data.get('first_name')} {user_data.get('last_name')}",
        "total_balance": _dec_to_float(balance.quantize(_QUANT)),
        "wallet_count": len(user_wallets)
    }


def get_wallet_balance(node_context: NodeContext, wallet_id: str) -> Dict[str, Any]:
    w_data = node_context.wallet_service.get_wallet(wallet_id)
    bal = _to_decimal(w_data.get("balance", 0.0))
    return {
        "wallet_id": wallet_id,
        "name": w_data.get("name"),
        "balance": _dec_to_float(bal.quantize(_QUANT)),
        "nonce": w_data.get("nonce", 0)
    }


def close_services(all_node_contexts: Dict[int, NodeContext]) -> None:
    for node_context in all_node_contexts.values():
        for attr_name in dir(node_context):
            if attr_name.endswith("_service"):
                service = getattr(node_context, attr_name)
                if service and hasattr(service, "close"):
                    try:
                        service.close()
                    except Exception as e:
                        logging.warning(f"Warning closing service {attr_name} on node: {e}")