#!/usr/bin/env python3
"""bootstrap_config.py - for BachiCoin bootstrap process."""

CURRENCY = "BACHI"
GENESIS_MINT_AMOUNT = 200000.0

SYSTEM_USERS = [
    {"name": "Genesis User", "email_prefix": "genesis.user", "user_type": "genesis", "home_node": 0},
    {"name": "Ledger System", "email_prefix": "ledger.system", "user_type": "ledger", "home_node": 0},
]

# These are the special GENESIS VALIDATORS who are pre-defined and created on all nodes at bootstrap.
GENESIS_VALIDATORS = [
    {"name": "Staker A", "email_prefix": "staker.a", "user_type": "validator", "home_node": 0},
    {"name": "Staker B", "email_prefix": "staker.b", "user_type": "validator", "home_node": 0},
    {"name": "Staker C", "email_prefix": "staker.c", "user_type": "validator", "home_node": 0},
    {"name": "Staker D", "email_prefix": "staker.d", "user_type": "validator", "home_node": 0},
]

BOOTSTRAP_USERS = [
    *SYSTEM_USERS,
    *[{**p, "user_type": "validator"} for p in GENESIS_VALIDATORS],
]
