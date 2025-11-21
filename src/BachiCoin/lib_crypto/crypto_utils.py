#!/usr/bin/env python3
"""crypto_utils.py: Provides a utility class for fundamental cryptographic operations."""

import base64
import base58
import hashlib
import hmac
import logging
import math
import os
import re
import sys
from typing import Dict, Optional, Union, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from Crypto.Hash import keccak
from coincurve.keys import PrivateKey, PublicKey

from BachiCoin.lib_crypto.crypto_config import CryptoConfig

logger = logging.getLogger(__name__)


class CryptoError(Exception):
    """Custom exception for cryptographic errors in this library."""
    pass


class CryptoUtils:
    """Utility class for basic cryptographic operations."""

    SUPPORTED_HASH_ALGOS = {"sha256", "sha384", "sha512"}

    def __init__(self, config: Optional[CryptoConfig] = None):
        """Initializes CryptoUtils with a given configuration."""
        self.config = config if config else CryptoConfig()
        logger.debug("CryptoUtils initialized with config")

    @staticmethod
    def hash_data(data: Union[str, bytes], algo: str = "sha256") -> bytes:
        """Hashes data using the specified algorithm."""
        if algo not in CryptoUtils.SUPPORTED_HASH_ALGOS:
            raise ValueError(f"Unsupported hashing algorithm: {algo}")
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.new(algo, data).digest()

    def hmac_data(self, key: Union[str, bytes], data: Union[str, bytes], algo: Optional[str] = None) -> bytes:
        """Computes an HMAC for the given data."""
        algo = algo or self.config.DEFAULT_HASH_ALGO
        if algo not in self.SUPPORTED_HASH_ALGOS:
            raise ValueError(f"Unsupported HMAC algorithm: {algo}")
        if isinstance(key, str):
            key = key.encode('utf-8')
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hmac.new(key, data, getattr(hashlib, algo)).digest()

    def _derive_key(self, key: Union[str, bytes], salt: bytes) -> bytes:
        """Derives a key using PBKDF2."""
        if isinstance(key, str):
            key = key.encode('utf-8')
        kdf = PBKDF2HMAC(
            algorithm=getattr(hashes, self.config.DEFAULT_HASH_ALGO.upper())(),
            length=self.config.KEY_LENGTH,
            salt=salt,
            iterations=self.config.ENCRYPTION_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(key)

    def encrypt_data(self, data: Union[str, bytes], key: Union[str, bytes], nonce: Optional[bytes] = None) -> Dict[str, bytes]:
        """Encrypts data using AES-GCM."""
        if isinstance(data, str):
            data = data.encode('utf-8')

        salt = os.urandom(self.config.SALT_LENGTH)
        derived_key = self._derive_key(key, salt)
        nonce = nonce or os.urandom(self.config.NONCE_LENGTH)
        aesgcm = AESGCM(derived_key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, data, None)

        tag = ciphertext_with_tag[-self.config.TAG_LENGTH:]
        ciphertext = ciphertext_with_tag[:-self.config.TAG_LENGTH]

        return {'ciphertext': ciphertext, 'nonce': nonce, 'salt': salt, 'tag': tag}

    def decrypt_data(self, encrypted_data: Dict[str, bytes], key: Union[str, bytes]) -> bytes:
        """Decrypts data encrypted with AES-GCM."""
        ciphertext = encrypted_data.get('ciphertext')
        nonce = encrypted_data.get('nonce')
        salt = encrypted_data.get('salt')
        tag = encrypted_data.get('tag')

        if not all([ciphertext, nonce, salt, tag]):
            raise ValueError("Incomplete encryption data provided. Required keys: 'ciphertext', 'nonce', 'salt', 'tag'.")

        derived_key = self._derive_key(key, salt)
        aesgcm = AESGCM(derived_key)
        return aesgcm.decrypt(nonce, ciphertext + tag, None)

    def sign_message(self, message: Union[str, bytes], private_key_pem: Union[str, bytes]) -> str:
        """Signs a message with a PEM-formatted private key (Non-recoverable DER format)."""
        if not isinstance(message, (str, bytes)):
            raise TypeError("message must be str or bytes")
        if not isinstance(private_key_pem, (str, bytes)):
            raise TypeError("private_key must be str or bytes")

        if isinstance(message, str):
            message = message.encode('utf-8')
        if isinstance(private_key_pem, str):
            private_key_pem = private_key_pem.encode('utf-8')

        try:
            key = serialization.load_pem_private_key(private_key_pem, password=None, backend=default_backend())

            if isinstance(key, ec.EllipticCurvePrivateKey):
                signature = key.sign(message, ec.ECDSA(hashes.SHA256()))
            elif isinstance(key, rsa.RSAPrivateKey):
                signature = key.sign(
                    message,
                    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                    hashes.SHA256()
                )
            else:
                raise CryptoError(f"Unsupported private key type: {type(key)}")

            return base64.b64encode(signature).decode('utf-8')
        except Exception as e:
            logger.error(f"Error signing message: {e}")
            raise CryptoError("Failed to sign message") from e

    def verify_signature(self, message: Union[str, bytes], signature: str, public_key_pem: Union[str, bytes]) -> bool:
        """Verifies a signature with a PEM-formatted public key."""
        if not isinstance(message, (str, bytes)):
            raise TypeError("message must be str or bytes")
        if not isinstance(signature, str):
            raise TypeError("signature must be a Base64 string")
        if not isinstance(public_key_pem, (str, bytes)):
            raise TypeError("public_key must be str or bytes")

        if isinstance(message, str):
            message = message.encode('utf-8')
        if isinstance(public_key_pem, str):
            public_key_pem = public_key_pem.encode('utf-8')

        try:
            signature_bytes = base64.b64decode(signature)
            key = serialization.load_pem_public_key(public_key_pem, backend=default_backend())

            if isinstance(key, ec.EllipticCurvePublicKey):
                key.verify(signature_bytes, message, ec.ECDSA(hashes.SHA256()))
            elif isinstance(key, rsa.RSAPublicKey):
                key.verify(
                    signature_bytes,
                    message,
                    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                    hashes.SHA256()
                )
            else:
                raise CryptoError(f"Unsupported public key type: {type(key)}")
            return True
        except InvalidSignature:
            logger.warning("Signature verification failed.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during signature verification: {e}")
            return False

    @staticmethod
    def constant_time_compare(val1: bytes, val2: bytes) -> bool:
        """Compares two byte strings in constant time to prevent timing attacks."""
        return hmac.compare_digest(val1, val2)

    @staticmethod
    def generate_address_from_public_key(pubkey_bytes: bytes) -> str:
        """Generates a standard Bitcoin-style P2PKH address from a public key."""
        sha256_hash = hashlib.sha256(pubkey_bytes).digest()
        ripemd160_hash = hashlib.new('ripemd160', sha256_hash).digest()
        payload = b'\x00' + ripemd160_hash
        return base58.b58encode_check(payload).decode('ascii')

    def validate_key_strength(self, key: Union[str, bytes]) -> None:
        """Validates the strength of a cryptographic key or password."""
        if not isinstance(key, (str, bytes)):
            raise TypeError("key must be str or bytes")

        key_str = key.decode('utf-8', errors='ignore') if isinstance(key, bytes) else key
        if len(key_str) < self.config.MIN_KEY_LENGTH:
            raise ValueError(f"Key is too short. Minimum length: {self.config.MIN_KEY_LENGTH}")

        if len(key_str) < 64:
            complexity_score = sum([
                1 if re.search(r'[A-Z]', key_str) else 0,
                1 if re.search(r'[a-z]', key_str) else 0,
                1 if re.search(r'\d', key_str) else 0,
                1 if re.search(r'[^A-Za-z0-9]', key_str) else 0
            ])
            if complexity_score < self.config.MIN_PASSWORD_COMPLEXITY:
                raise ValueError("Password doesn't meet complexity requirements. Use a mix of uppercase, lowercase, digits, and special characters.")

        char_set_size = 0
        if re.search(r'[a-z]', key_str): char_set_size += 26
        if re.search(r'[A-Z]', key_str): char_set_size += 26
        if re.search(r'\d', key_str): char_set_size += 10
        if re.search(r'[^A-Za-z0-9]', key_str): char_set_size += 32

        if char_set_size > 1:
            entropy = len(key_str) * math.log2(char_set_size)
            if entropy < self.config.MIN_KEY_ENTROPY:
                raise ValueError(f"Key entropy too low ({int(entropy)} bits). Consider a longer key with more varied characters.")

    def generate_key_pair(self, key_type: str = "ec", key_spec: Union[int, str] = None) -> Tuple[bytes, bytes]:
        """Generates a cryptographic key pair."""
        key_type_lower = key_type.lower()
        if key_type_lower not in {"rsa", "ec"}:
            raise ValueError(f"Unsupported key type: {key_type}")

        if key_type_lower == "rsa":
            key_size = key_spec or self.config.RSA_KEY_SIZE
            if not isinstance(key_size, int):
                raise TypeError("key_spec for RSA must be an integer (key size).")
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size, backend=default_backend())
        else:  # EC
            curve_name = key_spec or self.config.DEFAULT_EC_CURVE
            if not isinstance(curve_name, str):
                raise TypeError("key_spec for EC must be a string (curve name).")
            try:
                curve = getattr(ec, curve_name.upper())()
            except AttributeError:
                raise CryptoError(f"Unsupported EC curve: {curve_name}")
            private_key = ec.generate_private_key(curve=curve, backend=default_backend())

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return private_pem, public_pem

    @staticmethod
    def double_sha256(data: bytes) -> bytes:
        """Performs SHA256 twice, a common pattern in Bitcoin."""
        return hashlib.sha256(hashlib.sha256(data).digest()).digest()

    # =========================================================================
    # NEW AND CORRECTED METHODS FOR RECOVERABLE SIGNATURES (ETH-STYLE)
    # =========================================================================

    @staticmethod
    def sign_message_recoverable(message_hash: bytes, private_key_hex: str) -> str:
        """Signs a hash and returns a 65-byte recoverable signature (r,s,v) as a hex string."""
        private_key = PrivateKey.from_hex(private_key_hex)
        signature_bytes = private_key.sign_recoverable(message_hash, hasher=None)
        return signature_bytes.hex()

    @staticmethod
    def recover_public_key(message_hash: bytes, signature_hex: str) -> Optional[str]:
        """Recovers an uncompressed public key from an Ethereum-style recoverable signature."""
        try:
            signature_bytes = bytes.fromhex(signature_hex)
            public_key = PublicKey.from_signature_and_message(signature_bytes, message_hash, hasher=None)
            return public_key.format(compressed=False).hex()
        except Exception as e:
            logger.error(f"Failed to recover public key: {e}")
            return None

    @staticmethod
    def public_key_to_address(public_key_hex: str) -> str:
        """Converts an uncompressed public key to an Ethereum-style address."""
        public_key_bytes = bytes.fromhex(public_key_hex)
        # The first byte (0x04) of an uncompressed key is dropped for address calculation
        k_hash = keccak.new(digest_bits=256)
        k_hash.update(public_key_bytes[1:])
        address_bytes = k_hash.digest()[-20:]
        return "0x" + address_bytes.hex().lower()


if __name__ == '__main__':
    print("--- Smoke Test for crypto_utils.py (Recoverable Signatures) ---")

    # 1. Generate a new EC key pair for testing
    private_key_obj = PrivateKey()
    private_key_hex = private_key_obj.to_hex()
    public_key_obj = private_key_obj.public_key
    print(f"1. Generated a new key pair.")

    # 2. Create a message and hash it
    message = b"This is a test message for signature recovery."
    message_hash = CryptoUtils.hash_data(message, algo="sha256")
    print(f"2. Hashed message: {message_hash.hex()}")

    # 3. Sign the hash to get a recoverable signature
    try:
        signature_hex = CryptoUtils.sign_message_recoverable(message_hash, private_key_hex)
        print(f"3. Signed hash successfully.")
        print(f"   - Signature (r+s+v): {signature_hex}")
        assert len(signature_hex) == 130
        print("   PASS: Signature created in correct format.")
    except Exception as e:
        print(f"   FAIL: Could not create recoverable signature: {e}")
        sys.exit(1)

    # 4. Recover the public key from the signature
    try:
        recovered_pub_key_hex = CryptoUtils.recover_public_key(message_hash, signature_hex)
        print(f"4. Recovered public key.")
        print(f"   - Recovered Key: {recovered_pub_key_hex}")
        assert recovered_pub_key_hex is not None
        print("   PASS: Public key recovered successfully.")
    except Exception as e:
        print(f"   FAIL: Could not recover public key: {e}")
        sys.exit(1)

    # 5. Convert original public key to uncompressed hex for comparison
    original_pub_key_hex = public_key_obj.format(compressed=False).hex()
    print(f"5. Original public key for comparison: {original_pub_key_hex}")

    # 6. Compare original and recovered public keys
    print("6. Comparing original and recovered public keys...")
    if original_pub_key_hex == recovered_pub_key_hex:
        print("   PASS: Recovered public key matches the original.")
    else:
        print("   FAIL: Recovered public key DOES NOT MATCH the original.")
        sys.exit(1)

    # 7. Generate an address from the recovered public key
    try:
        recovered_address = CryptoUtils.public_key_to_address(recovered_pub_key_hex)
        print(f"7. Generated address from recovered key: {recovered_address}")
        assert recovered_address.startswith("0x") and len(recovered_address) == 42
        print("   PASS: Address generated successfully.")
    except Exception as e:
        print(f"   FAIL: Could not generate address: {e}")
        sys.exit(1)

    # 8. Generate an address from the original public key for final verification
    original_address = CryptoUtils.public_key_to_address(original_pub_key_hex)
    print(f"8. Generated address from original key:    {original_address}")

    # 9. Compare addresses
    print("9. Comparing original and recovered addresses...")
    if original_address == recovered_address:
        print("   PASS: Address from recovered key matches the original address.")
    else:
        print("   FAIL: Addresses DO NOT MATCH.")
        sys.exit(1)

    print("\n--- SMOKE TEST COMPLETED SUCCESSFULLY ---")