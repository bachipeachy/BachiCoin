#!/usr/bin/env python3
"""libtest_data.py — deterministic ground-truth balance calculator for test data.

This is a small, deterministic engine to compute expected wallet balances
after applying the TRANSACTION_SCHEDULE to an initial genesis mint.

Design notes:
- Genesis mint is credited to Ledger System -> mint wallet by default.
- Burn amounts are placed in Ledger System -> burn wallet (keeps totals closed).
- Gas is configurable (default 0.0 for deterministic tests).
- Uses canonical wallet types: 'private','business' for normal users and
  'mint','pool','burn' for the Ledger System.
"""

from typing import Dict, Any, List, Tuple
from decimal import Decimal, ROUND_HALF_EVEN

from BachiCoin.lib_bootstrap.bootstrap_config import GENESIS_MINT_AMOUNT, CURRENCY
from BachiCoin.lib_bootstrap.bootstrap_config import BOOTSTRAP_USERS as _BOOTSTRAP_USERS
from BachiCoin.lib_postprocess.postprocess_config import COMPUTATIONAL_DECIMAL_PLACES
from BachiCoin.lib_transaction.tx_config import TxType

# --- Test users and schedule (keeps your original schedule) ---
REGULAR_USERS = [
    {"name": "Gomer Adams", "email_prefix": "gomer.adams", "user_type": "individual", "home_node": 1},
    {"name": "Liam Adams", "email_prefix": "liam.adams", "user_type": "individual", "home_node": 2},
    {"name": "Isha Adams", "email_prefix": "isha.adams", "user_type": "individual", "home_node": 3},
    {"name": "Sophie Cyber", "email_prefix": "sophie.cyber", "user_type": "individual", "home_node": 4},
]

TRANSACTION_SCHEDULE = [
    # (kept identical to your provided schedule)
    {'slot': 1, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 2, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 3, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 4, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 5, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 6, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 7, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Sophie Cyber', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 8, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Sophie Cyber', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 9, 'tx_type': 'transfer', 'amount': 10000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Ledger System', 'wallet': 'pool'}, 'priority': 'urgent'},
    {'slot': 10, 'tx_type': 'reward', 'amount': 1000.0, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 11, 'tx_type': 'slash', 'amount': 1000.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 12, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'priority': 'standard'},
    {'slot': 13, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'priority': 'standard'},
    {'slot': 14, 'tx_type': 'burn', 'amount': 100.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 15, 'tx_type': 'stake', 'amount': 900.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'to_ref': {'user': 'Ledger System', 'wallet': 'pool'}, 'priority': 'standard'},
    {'slot': 16, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 17, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'priority': 'standard'},
    {'slot': 18, 'tx_type': 'unstake', 'amount': 500.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'pool'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 19, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 20, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'priority': 'standard'},
    {'slot': 21, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'business'}, 'priority': 'standard'},
    {'slot': 22, 'tx_type': 'burn', 'amount': 200.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'standard'},
    {'slot': 23, 'tx_type': 'stake', 'amount': 800.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'to_ref': {'user': 'Ledger System', 'wallet': 'pool'}, 'priority': 'standard'},
    {'slot': 24, 'tx_type': 'transfer', 'amount': 1000.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'private'}, 'priority': 'standard'},
]

# Combine users
ALL_TEST_USERS = [*_BOOTSTRAP_USERS, *REGULAR_USERS]

# ----- Helpers -----
def _dec(x: float) -> Decimal:
    """Decimal helper using the configured significant places."""
    q = Decimal(10) ** (-COMPUTATIONAL_DECIMAL_PLACES)
    return Decimal(str(x)).quantize(q, rounding=ROUND_HALF_EVEN)

def calculate_ground_truth_balances() -> Dict[str, Dict[str, float]]:
    """
    Computes expected final balances for all wallets based on TRANSACTION_SCHEDULE
    and GENESIS_MINT_AMOUNT.
    Returns a nested dictionary for granular validation: {user_name: {wallet_name: balance}}
    """
    # Initialize all wallets
    expected_balances: Dict[str, Dict[str, Decimal]] = {}

    # All users start with 0 in their wallets
    for user in ALL_TEST_USERS:
        expected_balances[user['name']] = {}
        if user['user_type'] not in ['ledger']:
            expected_balances[user['name']]['private'] = _dec(0.0)
            expected_balances[user['name']]['business'] = _dec(0.0)

    # Special system wallets
    expected_balances["Ledger System"] = {
        "mint": _dec(0.0),
        "pool": _dec(0.0),
        "burn": _dec(0.0)
    }

    # Apply Genesis Mint: Credited to the Ledger System's mint wallet
    expected_balances["Ledger System"]["mint"] += _dec(GENESIS_MINT_AMOUNT)

    # Apply transactions
    gas_fee = _dec(0.01)  # fixed fee for ground-truth calculation

    for tx in TRANSACTION_SCHEDULE:
        tx_type = tx['tx_type']
        amount = _dec(tx['amount'])

        from_user = tx.get('from_ref', {}).get('user')
        from_wallet = tx.get('from_ref', {}).get('wallet')
        to_user = tx.get('to_ref', {}).get('user')
        to_wallet = tx.get('to_ref', {}).get('wallet')

        # Apply transaction logic
        if tx_type == TxType.TRANSFER.value:
            if from_user and from_wallet:
                expected_balances[from_user][from_wallet] -= (amount + gas_fee)
                expected_balances["Ledger System"]["pool"] += gas_fee # Gas fee goes to the pool
            if to_user and to_wallet:
                expected_balances[to_user][to_wallet] += amount

        elif tx_type == TxType.REWARD.value:
            if to_user and to_wallet:
                expected_balances[to_user][to_wallet] += amount
            expected_balances["Ledger System"]["pool"] -= amount

        elif tx_type == TxType.SLASH.value:
            if from_user and from_wallet:
                expected_balances[from_user][from_wallet] -= (amount + gas_fee)
            expected_balances["Ledger System"]["pool"] += (amount + gas_fee) # Slashed amount and fee go to pool

        elif tx_type == TxType.BURN.value:
            if from_user and from_wallet:
                expected_balances[from_user][from_wallet] -= (amount + gas_fee)
                expected_balances["Ledger System"]["pool"] += gas_fee # Gas fee goes to the pool
            expected_balances["Ledger System"]["burn"] += amount

        elif tx_type == TxType.STAKE.value:
            if from_user and from_wallet:
                expected_balances[from_user][from_wallet] -= (amount + gas_fee)
            expected_balances["Ledger System"]["pool"] += (amount + gas_fee) # Staked amount and fee go to pool

        elif tx_type == TxType.UNSTAKE.value:
            if from_user == "Ledger System" and from_wallet == "pool":
                expected_balances["Ledger System"]["pool"] -= amount
            if to_user and to_wallet:
                expected_balances[to_user][to_wallet] += amount

        elif tx_type == TxType.MINT.value:
            if to_user and to_wallet:
                expected_balances[to_user][to_wallet] += amount

    # Convert final Decimal balances to float for external use
    final_balances: Dict[str, Dict[str, float]] = {}
    for user, wallets in expected_balances.items():
        final_balances[user] = {wallet: float(bal) for wallet, bal in wallets.items()}

    return final_balances


# --- Self-test / print ---
if __name__ == "__main__":
    wallet_balances = calculate_ground_truth_balances()
    
    print("=== Granular Wallet Balances (Ground Truth) ===")
    total_ledger_balance = Decimal('0.0')
    
    # Sort users for consistent output
    for user_name in sorted(wallet_balances.keys()):
        wallets = wallet_balances[user_name]
        user_total = sum(wallets.values())
        print(f"\n  👤 {user_name} (Total: {user_total:,.2f} {CURRENCY})")
        # Sort wallets for consistent output
        for wallet_name in sorted(wallets.keys()):
            balance = wallets[wallet_name]
            print(f"    - {wallet_name:<12}: {balance:15,.2f} {CURRENCY}")
            total_ledger_balance += _dec(balance)

    print("\n" + "-" * 50)
    print(f"  📊 Total Expected Ledger Balance: {float(total_ledger_balance):,.2f} {CURRENCY}")
    
    # Final conservation check
    assert round(total_ledger_balance, COMPUTATIONAL_DECIMAL_PLACES) == _dec(GENESIS_MINT_AMOUNT), \
        f"Total ledger balance {total_ledger_balance} does not equal genesis mint {GENESIS_MINT_AMOUNT}!"
        
    print("\n✅ Ground Truth Balance Calculation Test Passed!")
