#!/usr/bin/env python3
"""
hd_wallet.py

This module provides a high-level utility class for Hierarchical Deterministic (HD)
wallet operations, conforming to BIP39, BIP32, and BIP44 standards. It acts as
a wrapper around the 'bip_utils' library to ensure robust and standardized
implementations.
"""

import logging
import hashlib
from typing import Dict, Tuple

# IMPORTS FOR THE USER'S ENVIRONMENT (bip-utils v2.9.3)
from bip_utils import (
    Bip39MnemonicGenerator, Bip39MnemonicValidator, Bip39SeedGenerator, Bip39Languages,
    Bip32Secp256k1,
    Bip39EntropyGenerator
)

logger = logging.getLogger(__name__)


class HdWallet:
    """
    HD Wallet Utility Class for hierarchical deterministic wallet operations.
    This class is a static utility wrapper around the 'bip_utils' library.
    """

    @staticmethod
    def generate_mnemonic(strength_bits: int = 128) -> str:
        """
        Generates a new BIP-39 mnemonic phrase.
        """
        if strength_bits not in (128, 160, 192, 224, 256):
            raise ValueError("Mnemonic strength must be one of [128, 160, 192, 224, 256]")

        entropy = Bip39EntropyGenerator(strength_bits).Generate()

        # FINAL FIX: The FromEntropy method returns an object. We must convert it to a string.
        mnemonic_obj = Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(entropy)
        return mnemonic_obj.ToStr()

    @staticmethod
    def generate_mnemonic_from_seed(seed_phrase: str) -> str:
        """Deterministically generates a mnemonic from a seed phrase."""
        entropy = hashlib.sha256(seed_phrase.encode('utf-8')).digest()
        return Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(entropy).ToStr()

    @staticmethod
    def validate_mnemonic(mnemonic: str) -> bool:
        """
        Validates a BIP-39 mnemonic phrase.
        """
        if not isinstance(mnemonic, str):
            return False
        return Bip39MnemonicValidator(Bip39Languages.ENGLISH).IsValid(mnemonic)

    # Alias for backward compatibility
    is_valid_mnemonic = validate_mnemonic

    @staticmethod
    def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
        """
        Converts a BIP-39 mnemonic to a seed using PBKDF2.
        """
        if not HdWallet.validate_mnemonic(mnemonic):
            raise ValueError("Invalid BIP-39 mnemonic provided.")
        return Bip39SeedGenerator(mnemonic, Bip39Languages.ENGLISH).Generate(passphrase)

    @staticmethod
    def derive_from_path(seed: bytes, path: str) -> Tuple[bytes, bytes, bytes]:
        """
        Derives a private key, public key, and chain code from a seed and HD path.
        """
        if not isinstance(seed, bytes) or len(seed) < 16:
            raise ValueError("Seed must be a byte string of at least 16 bytes.")
        if not isinstance(path, str) or not path.startswith('m/'):
            raise ValueError("Path must be a string starting with 'm/'.")

        bip32_mst = Bip32Secp256k1.FromSeed(seed)
        bip32_child = bip32_mst.DerivePath(path)

        priv_key = bip32_child.PrivateKey().Raw().ToBytes()
        pub_key = bip32_child.PublicKey().RawCompressed().ToBytes()
        chain_code = bip32_child.ChainCode().ToBytes()

        return priv_key, pub_key, chain_code

    @staticmethod
    def get_extended_keys(seed: bytes, path: str) -> Dict[str, str]:
        """
        Derives and formats the extended private (xprv) and public (xpub) keys.
        """
        bip32_mst = Bip32Secp256k1.FromSeed(seed)
        bip32_child = bip32_mst.DerivePath(path)

        return {
            "xprv": bip32_child.PrivateKey().ToExtended(),
            "xpub": bip32_child.PublicKey().ToExtended(),
        }

    @staticmethod
    def generate_full_wallet(passphrase: str = "", path: str = "m/44'/0'/0'/0/0") -> Dict:
        """
        Generates a complete new wallet. Useful for testing and demonstration.
        """
        mnemonic = HdWallet.generate_mnemonic(128)
        seed = HdWallet.mnemonic_to_seed(mnemonic, passphrase)

        bip32_mst = Bip32Secp256k1.FromSeed(seed)
        bip32_child = bip32_mst.DerivePath(path)

        return {
            "mnemonic": mnemonic,
            "seed": seed.hex(),
            "path": path,
            "master_key": bip32_mst.PrivateKey().Raw().ToHex(),
            "master_chain_code": bip32_mst.ChainCode().ToHex(),
            "extended_keys": {
                "xprv": bip32_child.PrivateKey().ToExtended(),
                "xpub": bip32_child.PublicKey().ToExtended(),
            },
            "keypair": {
                "private_key": bip32_child.PrivateKey().Raw().ToHex(),
                "public_key": bip32_child.PublicKey().RawCompressed().ToHex(),
                "chain_code": bip32_child.ChainCode().ToHex(),
            }
        }
