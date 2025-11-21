#!/usr/bin/env python3
"""crossmodule_config.py - for BachiCoin lib code for cross module communication."""

from enum import Enum


class NetworkType(Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"

class Currency(Enum):
    """Defines the cryptocurrencies supported by the wallet."""
    BACHI = "BACHI"
    BTC = "BTC"
    ETH = "ETH"

