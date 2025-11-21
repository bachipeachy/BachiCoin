#!/usr/bin/env python3
"""Public API Facade for the BachiCoin Crypto Library."""

import hashlib
from typing import Union, Optional, Dict, Any, List

from BachiCoin.lib_crypto.crypto_config import CryptoConfig
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils
from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_crypto.key_manager import KeyManager, KeyManagerError as _KeyManagerError

KeyManagerError = _KeyManagerError

# ====================================================================
# === Grouped by Source File for Clarity and Maintainability ===
# ====================================================================

# --------------------------------------------------------------------
# --- Wrappers for: BachiCoin.lib_crypto.crypto_utils.py ---
# --------------------------------------------------------------------

def hash_data(data: Union[str, bytes], algo: str = "sha256") -> bytes:
    """Hashes data using the specified algorithm."""
    return CryptoUtils.hash_data(data, algo)

def sign_transaction(tx_hash_hex: str, private_key_hex: str) -> str:
    """Signs a transaction hash and returns a recoverable signature as a hex string with '0x' prefix."""
    if tx_hash_hex.startswith("0x"):
        tx_hash_hex = tx_hash_hex[2:]
    tx_hash_bytes = bytes.fromhex(tx_hash_hex)
    signature_hex = CryptoUtils.sign_message_recoverable(tx_hash_bytes, private_key_hex)
    return "0x" + signature_hex

def recover_public_key(tx_hash: bytes, signature_hex: str) -> Optional[str]:
    """Recovers the public key from a transaction hash and signature."""
    if signature_hex.startswith("0x"):
        signature_hex = signature_hex[2:]
    return CryptoUtils.recover_public_key(tx_hash, signature_hex)

def public_key_to_address(public_key_hex: str) -> str:
    """Converts a public key to a BachiCoin (Ethereum-style) address."""
    return CryptoUtils.public_key_to_address(public_key_hex)

# --------------------------------------------------------------------
# --- Wrappers for: BachiCoin.lib_crypto.hd_wallet.py ---
# --------------------------------------------------------------------

def generate_mnemonic(strength_bits: int = 128) -> str:
    """Generates a new BIP-39 mnemonic phrase."""
    return HdWallet.generate_mnemonic(strength_bits)

def generate_mnemonic_from_seed(seed_phrase: str) -> str:
    """Deterministically generates a mnemonic from a seed phrase."""
    return HdWallet.generate_mnemonic_from_seed(seed_phrase)

def validate_mnemonic(mnemonic: str) -> bool:
    """Validates a BIP-39 mnemonic phrase."""
    return HdWallet.validate_mnemonic(mnemonic)

# --------------------------------------------------------------------
# --- Wrappers for: BachiCoin.lib_crypto.key_manager.py ---
# --------------------------------------------------------------------

def create_key_manager(
        seed_or_mnemonic: Union[str, bytes] = None,
        passphrase: str = "",
        config: Optional[CryptoConfig] = None,
        watch_only: bool = False
) -> KeyManager:
    """Creates and initializes a KeyManager for all wallet operations."""
    return KeyManager(seed_or_mnemonic, passphrase, config, watch_only)

def create_key_manager_from_private_key(private_key: str) -> KeyManager:
    """Creates a KeyManager from a single private key."""
    return KeyManager(private_key=private_key)

def get_mnemonic(manager: KeyManager) -> Optional[str]:
    """Retrieves the mnemonic phrase from the KeyManager, if available."""
    return manager.get_mnemonic()

def derive_key(
        manager: KeyManager,
        path: Optional[str] = None,
        label: Optional[str] = None
) -> str:
    """Derives a new key from the HD wallet."""
    if path:
        return manager.derive_key_at_path(path, label)
    return manager.derive_key_from_hd_path(path, label)

def create_keypair(
        manager: KeyManager,
        label: Optional[str] = None,
        key_type: str = "ec"
) -> str:
    """Creates a new, non-HD (standalone) key pair inside the manager."""
    return manager.create_keypair(label, key_type)

def import_private_key(
        manager: KeyManager,
        private_key_pem: str,
        label: Optional[str] = None
) -> str:
    """Imports a standalone private key from PEM format into the manager."""
    return manager.import_private_key(private_key_pem, label)

def sign_message_der(manager: KeyManager, message: Union[str, bytes], label: str) -> str:
    """Signs a message and returns a non-recoverable DER-encoded signature."""
    return manager.sign_message_der(message, label)

def verify(manager: KeyManager, message: Union[str, bytes], signature: str, label: str) -> bool:
    """Verifies a signature using the public key associated with the given label."""
    return manager.verify(message, signature, label)

def get_public_key(manager: KeyManager, label: str) -> Optional[str]:
    """Retrieves the public key in PEM format for a given label."""
    return manager.get_public_key(label)

def get_private_key_hex(manager: KeyManager, label: str) -> Optional[str]:
    """Retrieves the private key in hex format for a given label."""
    return manager.get_private_key_hex(label)

def get_address(
        manager: KeyManager,
        label: str,
        eth_format: bool = False
) -> Optional[str]:
    """Retrieves the blockchain address for a given key label."""
    return manager.get_address(label, eth_format)

def list_keys(manager: KeyManager) -> List[str]:
    """Lists all key labels managed by the KeyManager."""
    return manager.list_keys()

def export_keys(manager: KeyManager) -> Dict[str, Any]:
    """Exports all keys managed by the KeyManager into a serializable dictionary."""
    return manager.export_keys()

def import_keys(manager: KeyManager, data: Dict[str, Any]):
    """Imports keys from a previously exported dictionary."""
    return manager.import_keys(data)

def rotate_key(manager: KeyManager, label: str) -> str:
    """Rotates an HD key by deriving a new key at the next index."""
    return manager.rotate_key(label)

def generate_crypto_addresses(
        manager: KeyManager,
        currency: str = "bachicoin",
        network: str = "mainnet",
        account_index: int = 0
) -> Dict[str, Any]:
    """Generates a pair of crypto addresses (EOA and UTXO-style)."""
    return manager.generate_crypto_addresses(currency, network, account_index)

def get_xprv_by_path(manager: KeyManager, path: str) -> str:
    """Gets the extended private key (xprv) for a given HD path."""
    return manager.get_xprv_by_path(path)

def get_xpub_by_path(manager: KeyManager, path: str) -> str:
    """Gets the extended public key (xpub) for a given HD path."""
    return manager.get_xpub_by_path(path)
