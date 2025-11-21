#!/usr/bin/env python3
"""
key_manager.py

This module defines the KeyManager class, the core of the wallet. It manages
the lifecycle of cryptographic keys, including derivation, storage, signing,
and address generation, supporting both Bitcoin and BachiCoin (ETH-style)
formats.
"""

from datetime import datetime, timezone
from typing import Union, Optional, Dict, Any, List

# Correctly import Keccak-256 for Ethereum address generation
from Crypto.Hash import keccak
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from BachiCoin.lib_crypto.crypto_config import CoinConstants, CryptoConfig
from BachiCoin.lib_crypto.hd_wallet import HdWallet
from BachiCoin.lib_crypto.key_pair import KeyPair


class KeyManagerError(Exception):
    """Custom exception for errors within the KeyManager."""
    pass


class KeyManager:
    """
    Manages cryptographic keys for wallet operations.
    Handles key derivation, signing, verification, storage & rotation.
    """

    def __init__(self,
                 seed_or_mnemonic: Union[str, bytes] = None,
                 passphrase: str = "",
                 config: Optional[CryptoConfig] = None,
                 watch_only: bool = False,
                 private_key: Optional[str] = None):
        """
        Initializes the KeyManager.
        """
        self.config = config or CryptoConfig()
        self.watch_only = watch_only
        self._keys_by_label: Dict[str, Dict[str, Any]] = {}
        self._mnemonic: Optional[str] = None
        self._seed: Optional[bytes] = None
        self._passphrase = passphrase

        if private_key:
            if seed_or_mnemonic is not None:
                raise KeyManagerError("Cannot provide both a seed/mnemonic and a private key.")
            pass # Placeholder for now

        if self.watch_only and seed_or_mnemonic is not None:
            raise KeyManagerError("Cannot provide seed/mnemonic in watch-only mode.")

        if seed_or_mnemonic is None:
            if self.watch_only:
                self._mnemonic = None
                self._seed = None
            else:
                self._mnemonic = HdWallet.generate_mnemonic(strength_bits=128)
                self._seed = HdWallet.mnemonic_to_seed(self._mnemonic, passphrase=self._passphrase)
        elif isinstance(seed_or_mnemonic, str):
            if not HdWallet.is_valid_mnemonic(seed_or_mnemonic):
                raise ValueError("Invalid mnemonic provided.")
            self._mnemonic = seed_or_mnemonic
            self._seed = HdWallet.mnemonic_to_seed(self._mnemonic, passphrase=self._passphrase)
        elif isinstance(seed_or_mnemonic, bytes):
            self._seed = seed_or_mnemonic
        else:
            raise TypeError("Invalid type for seed_or_mnemonic. Must be str, bytes, or None.")

    def get_mnemonic(self) -> Optional[str]:
        """Returns the mnemonic phrase, if one was generated or provided."""
        return self._mnemonic

    def _get_account_path(self) -> str:
        """Returns the base account path for BachiCoin."""
        return f"m/44'/{CoinConstants.BACHICOIN_COIN_TYPE}'/0'"

    def _generate_eth_address(self, key_pair: KeyPair) -> str:
        """Generates a correct Ethereum-style address from a KeyPair using Keccak-256."""
        if not isinstance(key_pair._public_key, ec.EllipticCurvePublicKey):
            raise TypeError("Ethereum addresses can only be generated from EC keys.")

        public_key_obj = key_pair._public_key

        public_key_bytes = public_key_obj.public_numbers().x.to_bytes(32, 'big') + \
                           public_key_obj.public_numbers().y.to_bytes(32, 'big')

        k_hash = keccak.new(digest_bits=256)
        k_hash.update(public_key_bytes)
        address_bytes = k_hash.digest()[-20:]

        return "0x" + address_bytes.hex().lower()

    def _get_next_address_index(self) -> int:
        """Calculates the next unused address index."""
        current_max = -1
        for key_info in self._keys_by_label.values():
            path = key_info.get("path")
            if path and path.startswith(self._get_account_path()):
                try:
                    index = int(path.split('/')[-1])
                    if index > current_max:
                        current_max = index
                except (ValueError, IndexError):
                    continue
        return current_max + 1

    def _derive_and_store_key(self, path: str, label: str) -> str:
        """Private helper to derive a key from a path, create a KeyPair, and store it."""
        if self.watch_only:
            raise KeyManagerError("Cannot derive private keys in watch-only mode.")
        if label in self._keys_by_label:
            raise ValueError(f"Label '{label}' already exists.")

        priv_key_bytes, _, _ = HdWallet.derive_from_path(self._seed, path)

        priv_key_obj = ec.derive_private_key(int.from_bytes(priv_key_bytes, "big"), ec.SECP256K1(), default_backend())

        key_pair = KeyPair.from_private_key_obj(priv_key_obj)

        self._keys_by_label[label] = {
            "path": path,
            "key_pair": key_pair,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"coin": "bachicoin", "derivation": "hd"}
        }
        return label

    def derive_key_from_hd_path(self, path: Optional[str] = None, label: Optional[str] = None) -> str:
        """Derives a new key from the next available index in the HD path or a specific path."""
        if path is None:
            index = self._get_next_address_index()
            path = f"{self._get_account_path()}/0/{index}"

        label = label or f"key_{len(self._keys_by_label)}"
        return self._derive_and_store_key(path, label)

    def derive_key_at_path(self, path: str, label: Optional[str] = None) -> str:
        """Derives a key at a specific, explicit HD path."""
        label = label or f"key_at_{path.replace('/', '_')}"
        return self._derive_and_store_key(path, label)

    def create_keypair(self, label: Optional[str] = None, key_type: str = "ec") -> str:
        """Creates a new, non-HD (standalone) key pair."""
        if self.watch_only:
            raise KeyManagerError("Cannot create private keys in watch-only mode.")

        key_pair = KeyPair.generate(key_type=key_type)
        label = label or f"generated_{len(self._keys_by_label)}"
        self._keys_by_label[label] = {
            "path": None,
            "key_pair": key_pair,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"standalone": True, "type": key_type}
        }
        return label

    def import_private_key(self, private_key_pem: str, label: Optional[str] = None) -> str:
        """Imports a standalone private key from PEM format."""
        if self.watch_only:
            raise KeyManagerError("Cannot import private keys in watch-only mode.")

        key_pair = KeyPair.from_pem(private_key_pem)
        label = label or f"imported_{len(self._keys_by_label)}"
        self._keys_by_label[label] = {
            "path": None,
            "key_pair": key_pair,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"imported": True}
        }
        return label

    def sign_message_der(self, message: Union[str, bytes], label: str) -> str:
        """Signs a message and returns a non-recoverable DER-encoded signature."""
        if self.watch_only:
            raise KeyManagerError("Cannot sign in watch-only mode.")
        entry = self.get_key_by_label(label)
        if not entry:
            raise ValueError(f"No key found for label: {label}")

        key_pair: KeyPair = entry["key_pair"]
        return key_pair.sign(message)

    def verify(self, message: Union[str, bytes], signature: str, label: str) -> bool:
        """Verifies a signature using the public key for the given label."""
        entry = self.get_key_by_label(label)
        if not entry:
            raise ValueError(f"No key found for label: {label}")

        key_pair: KeyPair = entry["key_pair"]
        return key_pair.verify(message, signature)

    def get_xprv_by_path(self, path: str) -> str:
        """Gets the extended private key (xprv) for a given HD path."""
        if self.watch_only:
            raise KeyManagerError("Cannot get extended private key in watch-only mode.")
        if not self._seed:
            raise KeyManagerError("Seed is not available to derive extended key.")
        return HdWallet.get_extended_keys(self._seed, path)["xprv"]

    def get_xpub_by_path(self, path: str) -> str:
        """Gets the extended public key (xpub) for a given HD path."""
        if not self._seed:
            raise KeyManagerError("Seed is not available to derive extended key.")
        return HdWallet.get_extended_keys(self._seed, path)["xpub"]

    def get_key_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        """Retrieves the full dictionary of information for a given key label."""
        return self._keys_by_label.get(label)

    def get_public_key(self, label: str) -> Optional[str]:
        """Retrieves the public key in PEM format for a given label."""
        entry = self.get_key_by_label(label)
        return entry["key_pair"].public_key_pem if entry else None

    def get_private_key_hex(self, label: str) -> Optional[str]:
        """Retrieves the private key in a zero-padded, 32-byte hex format."""
        entry = self.get_key_by_label(label)
        if not entry:
            return None
        key_pair: KeyPair = entry["key_pair"]
        private_key_obj = serialization.load_pem_private_key(
            key_pair.private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        if isinstance(private_key_obj, ec.EllipticCurvePrivateKey):
            return private_key_obj.private_numbers().private_value.to_bytes(32, 'big').hex()
        return None

    def get_address(self, label: str, eth_format: bool = False) -> Optional[str]:
        """Retrieves the blockchain address for a given label."""
        entry = self.get_key_by_label(label)
        if not entry:
            return None

        key_pair: KeyPair = entry["key_pair"]
        if eth_format:
            return self._generate_eth_address(key_pair)
        else:
            return key_pair.get_address()

    def list_keys(self) -> List[str]:
        """Lists all key labels managed by the KeyManager."""
        return list(self._keys_by_label.keys())

    def export_keys(self) -> Dict[str, Any]:
        """Exports all keys managed by the KeyManager into a serializable dictionary."""
        exported_data = {}
        for label, entry in self._keys_by_label.items():
            key_pair: KeyPair = entry["key_pair"]
            exported_data[label] = {
                "path": entry.get("path"),
                "created_at": entry["created_at"],
                "metadata": entry["metadata"],
                "key_pair": key_pair.to_dict()
            }
        return exported_data

    def import_keys(self, data: Dict[str, Any]):
        """Imports keys from a previously exported dictionary."""
        for label, entry in data.items():
            if self.watch_only and "private_key_pem" in entry["key_pair"]:
                entry["key_pair"]["private_key_pem"] = None

            key_pair = KeyPair.from_dict(entry["key_pair"])
            self._keys_by_label[label] = {
                "path": entry.get("path"),
                "key_pair": key_pair,
                "address": key_pair.get_address(),
                "created_at": entry["created_at"],
                "metadata": entry["metadata"]
            }

    def rotate_key(self, label: str) -> str:
        """Rotates an HD key by deriving a new key at the next index."""
        entry = self.get_key_by_label(label)
        if not entry or "path" not in entry or not entry["path"]:
            raise ValueError(f"No HD key found for label: {label} to rotate.")

        base_path = entry["path"].rsplit('/', 1)[0]
        last_index = int(entry["path"].split('/')[-1])
        new_index = last_index + 1
        new_path = f"{base_path}/{new_index}"

        new_label = f"{label}_rotated_{new_index}"
        return self.derive_key_at_path(new_path, new_label)

    def check_rotation_needed(self) -> List[str]:
        """Checks for keys that have exceeded their configured rotation interval."""
        now = datetime.now(timezone.utc)
        rotation_days = getattr(self.config, "key_rotation_interval", 30)
        needs_rotation = []
        for label, entry in self._keys_by_label.items():
            created_at_str = entry["created_at"]
            created_at = datetime.fromisoformat(created_at_str)
            age = now - created_at
            if age.days > rotation_days:
                needs_rotation.append(label)
        return needs_rotation

    def generate_crypto_addresses(self, currency: str, network: str, account_index: int = 0) -> Dict[str, Any]:
        """Generates a pair of crypto addresses (EOA and UTXO-style)."""
        account_path = f"m/44'/{CoinConstants.BACHICOIN_COIN_TYPE}'/{account_index}'"
        eoa_path = f"{account_path}/0/0"
        utxo_path = f"{account_path}/1/0"

        eoa_label = self.derive_key_at_path(eoa_path, f"crypto_{account_index}_eoa")
        utxo_label = self.derive_key_at_path(utxo_path, f"crypto_{account_index}_utxo")

        eoa_eth_address = self.get_address(eoa_label, eth_format=True)
        utxo_eth_address = self.get_address(utxo_label, eth_format=True)

        eoa_pubkey = self.get_public_key(eoa_label)
        utxo_pubkey = self.get_public_key(utxo_label)

        addresses = {
            "eoa": {
                "address": eoa_eth_address,
                "path": eoa_path,
                "format": "hex",
                "type": "eoa",
                "label": eoa_label,
                "public_key": eoa_pubkey,
                "created_at": self._keys_by_label[eoa_label]["created_at"],
            },
            "utxo": {
                "address": utxo_eth_address,
                "path": utxo_path,
                "format": "hex",
                "type": "utxo",
                "label": utxo_label,
                "public_key": utxo_pubkey,
                "created_at": self._keys_by_label[utxo_label]["created_at"],
            }
        }

        return addresses

    def generate_bitcoin_address(self, label: str) -> str:
        """Generates a Bitcoin-format (P2PKH) address for a given key label."""
        address = self.get_address(label, eth_format=False)
        if not address:
            raise ValueError(f"Key label not found: {label}")
        return address
