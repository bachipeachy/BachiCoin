#!/usr/bin/env python3
"""test data definitions for BachiCoin automated testing."""


# These are the REGULAR users who will be created just-in-time on their nodes.
REGULAR_USERS = [
    {"name": "Gomer Adams", "email_prefix": "gomer.adams", "user_type": "individual", "home_node": 1},
    {"name": "Liam Adams", "email_prefix": "liam.adams", "user_type": "individual", "home_node": 2},
    {"name": "Isha Adams", "email_prefix": "isha.adams", "user_type": "individual", "home_node": 3},
    {"name": "Sophie Cyber", "email_prefix": "sophie.cyber", "user_type": "individual", "home_node": 4},
]

TRANSACTION_SCHEDULE = [
    # --- Initial Funding Transfers (from Ledger System Mint Wallet, now acting as a treasury) ---
    {'slot': 1, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 2, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 3, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 4, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Liam Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 5, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 6, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Isha Adams', 'wallet': 'business'}, 'priority': 'urgent'},
    {'slot': 7, 'tx_type': 'transfer', 'amount': 6000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Sophie Cyber', 'wallet': 'private'}, 'priority': 'urgent'},
    {'slot': 8, 'tx_type': 'transfer', 'amount': 4000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Sophie Cyber', 'wallet': 'business'}, 'priority': 'urgent'},
    # --- Pool Funding (from Ledger System Mint Wallet to Pool Wallet) ---
    {'slot': 9, 'tx_type': 'transfer', 'amount': 10000.0, 'from_ref': {'user': 'Ledger System', 'wallet': 'mint'}, 'to_ref': {'user': 'Ledger System', 'wallet': 'pool'}, 'priority': 'urgent'},
    # --- System Rewards (to a validator, e.g., Gomer) ---
    {'slot': 10, 'tx_type': 'reward', 'amount': 1000.0, 'to_ref': {'user': 'Gomer Adams', 'wallet': 'private'}, 'priority': 'standard'},
    # --- System Slash (from a validator, e.g., Liam) ---
    {'slot': 11, 'tx_type': 'slash', 'amount': 1000.0, 'from_ref': {'user': 'Liam Adams', 'wallet': 'private'}, 'priority': 'urgent'},
    # --- User-initiated transactions ---
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
