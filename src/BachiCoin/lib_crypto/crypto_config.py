#!/usr/bin/env python3
"""
crypto_config.py

This module defines three configuration classes for the crypto library:

- CoinConstants: Immutable network and address constants for supported blockchains.
- CryptoConfig: Core defaults for cryptographic operations (hashing, encryption).
- KeyConfig: User-tunable settings for HD wallets and key management.
"""


class CoinConstants:
    """
    Immutable constants for BachiCoin, Bitcoin, and network compatibility.
    These are defined as class-level attributes for direct, efficient access.
    """

    # BIP32/44 basics
    HARDENED_INDEX_OFFSET = 0x80000000
    BIP32_SEED_HMAC_KEY = b"Bitcoin seed"
    BIP44_PURPOSE = 44

    # Coin Types (SLIP-44)
    BTC_COIN_TYPE_MAINNET = 0
    BTC_COIN_TYPE_TESTNET = 1
    # NOTE: 66 (0x42) is not officially registered. Using for BachiCoin.
    BACHICOIN_COIN_TYPE = 66

    # Bitcoin Address Prefixes (Version Bytes)
    BTC_P2PKH_PREFIX_MAINNET = b'\x00'
    BTC_P2PKH_PREFIX_TESTNET = b'\x6f'
    BTC_P2SH_PREFIX_MAINNET = b'\x05'
    BTC_P2SH_PREFIX_TESTNET = b'\xc4'
    BTC_BECH32_HRP_MAINNET = "bc"
    BTC_BECH32_HRP_TESTNET = "tb"

    # BachiCoin Address Prefixes (Version Bytes)
    BACHICOIN_P2PKH_PREFIX_MAINNET = b'\x1a'
    BACHICOIN_P2PKH_PREFIX_TESTNET = b'\x6a'
    BACHICOIN_P2SH_PREFIX_MAINNET = b'\x2a'
    BACHICOIN_P2SH_PREFIX_TESTNET = b'\xc2'
    # Using unique HRPs to avoid confusion with Bitcoin
    BACHICOIN_BECH32_HRP_MAINNET = "bcn"
    BACHICOIN_BECH32_HRP_TESTNET = "tbn"

    # General constants
    ADDRESS_FORMATS = ["p2pkh", "p2sh-p2wpkh", "p2wpkh", "p2tr"]
    VALID_ENTROPY_BITS = [128, 160, 192, 224, 256]

    # BIP-32 version bytes (mainnet/testnet xprv/xpub)
    BIP32_VERSIONS = {
        "xprv_main": b"\x04\x88\xAD\xE4",
        "xpub_main": b"\x04\x88\xB2\x1E",
        "xprv_test": b"\x04\x35\x83\x94",
        "xpub_test": b"\x04\x35\x87\xCF",
    }


class CryptoConfig:
    """
    Core defaults and constraints for cryptographic operations.
    An instance of this class holds the configuration state.
    """

    # --- Default Algorithm and Strength Parameters ---
    DEFAULT_HASH_ALGO = "sha256"
    DEFAULT_ENCRYPTION_ALGO = "aes-256-gcm"
    ENCRYPTION_ITERATIONS = 100000
    KEY_LENGTH = 32
    NONCE_LENGTH = 12
    TAG_LENGTH = 16
    SALT_LENGTH = 16
    RSA_KEY_SIZE = 2048
    DEFAULT_EC_CURVE = "SECP256K1"  # CRITICAL: Changed to standard curve for BTC/ETH
    MIN_KEY_LENGTH = 12
    MIN_PASSWORD_COMPLEXITY = 3
    MIN_KEY_ENTROPY = 64

    # REMOVED: BYPASS_ENCRYPTION_DEFAULT - This was a critical security vulnerability.
    # REMOVED: DEFAULT_TEST_PASSWORD - This was an unsafe default.

    def __init__(self, **kwargs):
        """Initializes config, allowing overrides for any class-level attribute."""
        for key, value in kwargs.items():
            # Ensure we only set attributes that are defined in the class
            if hasattr(self, key.upper()):
                setattr(self, key.upper(), value)
            else:
                raise AttributeError(f"Unknown configuration parameter: {key}")

    def to_dict(self) -> dict:
        """Returns all public, uppercase attributes as a dictionary."""
        return {
            key: getattr(self, key) for key in dir(self)
            if not key.startswith('_') and key.isupper()
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'CryptoConfig':
        """Creates a CryptoConfig instance from a dictionary."""
        return cls(**config_dict)

    @classmethod
    def testing_config(cls) -> 'CryptoConfig':
        """Returns a new CryptoConfig instance with values suitable for testing."""
        return cls(
            ENCRYPTION_ITERATIONS=100,  # Reduced for speed
            MIN_KEY_LENGTH=8,
            MIN_PASSWORD_COMPLEXITY=1,
            MIN_KEY_ENTROPY=32
        )


class KeyConfig:
    """
    User-configurable settings for HD wallets, derivation, rotation, and reuse.
    Provides properties that dynamically return correct values based on coin and network.
    """

    def __init__(self,
                 testnet=True,
                 coin="bitcoin",
                 last_index=-1,
                 max_address_gap=20,
                 bip39_passphrase="",
                 default_address_format="p2wpkh",
                 entropy_bits=256,
                 key_rotation_interval=30,
                 address_reuse_limit=1,
                 purpose=44,
                 account=0,
                 change=0,
                 address_index=0):
        self.testnet = testnet
        self.coin = coin.lower()
        self.last_index = last_index
        self.max_address_gap = max_address_gap
        self.bip39_passphrase = bip39_passphrase
        self.default_address_format = default_address_format
        self.entropy_bits = entropy_bits
        self.key_rotation_interval = key_rotation_interval
        self.address_reuse_limit = address_reuse_limit
        self.purpose = purpose
        self.account = account
        self.change = change
        self.address_index = address_index

        self.validate()

    def get_derivation_path(self) -> str:
        """Constructs the full BIP-44 derivation path string."""
        coin_type = self.coin_type
        return f"m/{self.purpose}'/{coin_type}'/{self.account}'/{self.change}/{self.address_index}"

    def to_dict(self) -> dict:
        """Returns a dictionary representation of the configuration."""
        return vars(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'KeyConfig':
        """Creates a KeyConfig instance from a dictionary."""
        return cls(**data)

    @property
    def coin_type(self) -> int:
        """Returns the SLIP-44 coin type based on the configured coin and network."""
        if self.coin == "bitcoin":
            return CoinConstants.BTC_COIN_TYPE_TESTNET if self.testnet else CoinConstants.BTC_COIN_TYPE_MAINNET
        elif self.coin == "bachicoin":
            return CoinConstants.BACHICOIN_COIN_TYPE
        # Default to Bitcoin if coin is unknown
        return CoinConstants.BTC_COIN_TYPE_TESTNET if self.testnet else CoinConstants.BTC_COIN_TYPE_MAINNET

    @property
    def p2pkh_prefix(self) -> bytes:
        """Returns the correct P2PKH address prefix."""
        if self.coin == "bitcoin":
            return CoinConstants.BTC_P2PKH_PREFIX_TESTNET if self.testnet else CoinConstants.BTC_P2PKH_PREFIX_MAINNET
        elif self.coin == "bachicoin":
            return CoinConstants.BACHICOIN_P2PKH_PREFIX_TESTNET if self.testnet else CoinConstants.BACHICOIN_P2PKH_PREFIX_MAINNET
        # Default to Bitcoin if coin is unknown
        return CoinConstants.BTC_P2PKH_PREFIX_TESTNET if self.testnet else CoinConstants.BTC_P2PKH_PREFIX_MAINNET

    @property
    def p2sh_prefix(self) -> bytes:
        """Returns the correct P2SH address prefix."""
        if self.coin == "bitcoin":
            return CoinConstants.BTC_P2SH_PREFIX_TESTNET if self.testnet else CoinConstants.BTC_P2SH_PREFIX_MAINNET
        elif self.coin == "bachicoin":
            return CoinConstants.BACHICOIN_P2SH_PREFIX_TESTNET if self.testnet else CoinConstants.BACHICOIN_P2SH_PREFIX_MAINNET
        # Default to Bitcoin if coin is unknown
        return CoinConstants.BTC_P2SH_PREFIX_TESTNET if self.testnet else CoinConstants.BTC_P2SH_PREFIX_MAINNET

    @property
    def bech32_hrp(self) -> str:
        """Returns the correct Bech32 Human-Readable Part (HRP)."""
        if self.coin == "bitcoin":
            return CoinConstants.BTC_BECH32_HRP_TESTNET if self.testnet else CoinConstants.BTC_BECH32_HRP_MAINNET
        elif self.coin == "bachicoin":
            return CoinConstants.BACHICOIN_BECH32_HRP_TESTNET if self.testnet else CoinConstants.BACHICOIN_BECH32_HRP_MAINNET
        # Default to Bitcoin if coin is unknown
        return CoinConstants.BTC_BECH32_HRP_TESTNET if self.testnet else CoinConstants.BTC_BECH32_HRP_MAINNET

    def validate(self) -> bool:
        """Performs validation of all configuration attributes."""
        if self.entropy_bits not in CoinConstants.VALID_ENTROPY_BITS:
            raise ValueError(f"Entropy bits must be one of {CoinConstants.VALID_ENTROPY_BITS}")
        if self.default_address_format not in CoinConstants.ADDRESS_FORMATS:
            raise ValueError(f"Address format must be one of {CoinConstants.ADDRESS_FORMATS}")
        if self.coin not in ["bitcoin", "bachicoin"]:
            raise ValueError("Coin must be 'bitcoin' or 'bachicoin'")
        if self.max_address_gap < 1:
            raise ValueError("Address gap must be at least 1")
        if self.address_reuse_limit < 1:
            raise ValueError("Address reuse limit must be at least 1")
        if self.purpose not in [44, 49, 84]:
            raise ValueError("Purpose must be one of [44, 49, 84] for BIP44, BIP49, BIP84")
        if self.account < 0:
            raise ValueError("Account index must be non-negative")
        if self.change not in [0, 1]:
            raise ValueError("Change must be 0 (external) or 1 (internal)")
        if self.address_index < 0:
            raise ValueError("Address index must be non-negative")
        return True
