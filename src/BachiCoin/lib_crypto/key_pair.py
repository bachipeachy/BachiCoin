#!/usr/bin/env python3
"""
key_pair.py

This module defines the KeyPair class, which encapsulates a private/public
key pair and provides methods for signing, verification, and address derivation.
"""

import base64
import logging
from typing import Dict, Optional, Union

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ec
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key, load_pem_public_key,
    Encoding, PrivateFormat, PublicFormat, NoEncryption,
)

from BachiCoin.lib_crypto.crypto_config import CryptoConfig
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils, CryptoError

logger = logging.getLogger(__name__)


class KeyPair:
    """
    Handles a private/public key pair, including signing, verification, and address derivation.

    This class now caches the underlying cryptography key objects for improved
    performance, loading them from PEM strings only on first use.
    """

    def __init__(self,
                 private_key_pem: str,
                 public_key_pem: str,
                 address: Optional[str] = None,
                 key_type: Optional[str] = None):
        """
        Initializes the KeyPair.

        Args:
            private_key_pem: The private key as a PEM-formatted string.
            public_key_pem: The public key as a PEM-formatted string.
            address: An optional pre-derived address.
            key_type: An optional key type ('ec' or 'rsa').
        """
        if not isinstance(private_key_pem, str) or not isinstance(public_key_pem, str):
            raise TypeError("Private and public keys must be PEM strings.")

        self.private_key_pem = private_key_pem
        self.public_key_pem = public_key_pem
        self._address = address
        self._key_type = key_type

        # Caching for performance: key objects are loaded on first use
        self._private_key_obj: Optional[Union[rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey]] = None
        self._public_key_obj: Optional[Union[rsa.RSAPublicKey, ec.EllipticCurvePublicKey]] = None
        self.config = CryptoConfig()

    @property
    def _private_key(self) -> Union[rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey]:
        """Lazy-loads and caches the private key object from its PEM representation."""
        if self._private_key_obj is None:
            try:
                self._private_key_obj = load_pem_private_key(
                    self.private_key_pem.encode('utf-8'),
                    password=None,
                    backend=default_backend()
                )
            except Exception as e:
                logger.error(f"Failed to load private key from PEM: {e}")
                raise CryptoError("Invalid private key PEM format.") from e
        return self._private_key_obj

    @property
    def _public_key(self) -> Union[rsa.RSAPublicKey, ec.EllipticCurvePublicKey]:
        """Lazy-loads and caches the public key object from its PEM representation."""
        if self._public_key_obj is None:
            try:
                self._public_key_obj = load_pem_public_key(
                    self.public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )
            except Exception as e:
                logger.error(f"Failed to load public key from PEM: {e}")
                raise CryptoError("Invalid public key PEM format.") from e
        return self._public_key_obj

    @property
    def key_type(self) -> str:
        """Determines the key type ('ec' or 'rsa') from the loaded key object."""
        if self._key_type is None:
            if isinstance(self._private_key, ec.EllipticCurvePrivateKey):
                self._key_type = "ec"
            elif isinstance(self._private_key, rsa.RSAPrivateKey):
                self._key_type = "rsa"
            else:
                self._key_type = "unknown"
        return self._key_type

    @classmethod
    def generate(cls, key_type: str = "ec", **kwargs) -> 'KeyPair':
        """
        Generates a new cryptographic key pair.

        Args:
            key_type: The type of key to create ("ec" or "rsa"). Defaults to "ec".
            **kwargs: For "ec", can specify 'curve' (e.g., "SECP256K1").
                      For "rsa", can specify 'key_size' (e.g., 2048).

        Returns:
            A new KeyPair instance.
        """
        config = CryptoConfig()
        key_type_lower = key_type.lower()

        if key_type_lower == "rsa":
            key_size = kwargs.get('key_size', config.RSA_KEY_SIZE)
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
        elif key_type_lower == "ec":
            # Standardize on SECP256K1 as the default for crypto applications
            curve_name = kwargs.get('curve', config.DEFAULT_EC_CURVE)
            try:
                curve = getattr(ec, curve_name)()
            except AttributeError:
                raise CryptoError(f"Unsupported EC curve: {curve_name}")
            private_key = ec.generate_private_key(
                curve=curve,
                backend=default_backend()
            )
        else:
            raise ValueError(f"Unsupported key type: {key_type}")

        # Standardize on PKCS8 for private key serialization
        private_key_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption()
        ).decode('utf-8')

        public_key_pem = private_key.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return cls(
            private_key_pem=private_key_pem,
            public_key_pem=public_key_pem,
            key_type=key_type_lower
        )

    @classmethod
    def from_private_key_obj(cls, key_obj: Union[rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey]) -> "KeyPair":
        """Constructs a KeyPair from a cryptography private key object."""
        if not isinstance(key_obj, (rsa.RSAPrivateKey, ec.EllipticCurvePrivateKey)):
            raise TypeError("key_obj must be an RSA or EC private key object.")

        private_pem = key_obj.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,  # Use modern, standard format
            encryption_algorithm=NoEncryption()
        ).decode('utf-8')

        public_pem = key_obj.public_key().public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        key_type = "ec" if isinstance(key_obj, ec.EllipticCurvePrivateKey) else "rsa"
        return cls(private_pem, public_pem, key_type=key_type)

    @classmethod
    def from_pem(cls, private_key_pem: str) -> "KeyPair":
        """
        Constructs KeyPair from a PEM-encoded private key string.
        The public key is automatically derived.
        """
        try:
            private_key = load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None,
                backend=default_backend()
            )
            # Delegate to the object-based constructor
            return cls.from_private_key_obj(private_key)
        except Exception as e:
            logger.error(f"Failed to load key from PEM string: {e}")
            raise CryptoError("Could not construct KeyPair from PEM.") from e

    def get_address(self) -> str:
        """
        Gets the blockchain address derived from the public key.
        Caches the address after the first generation.
        """
        if self._address is None:
            public_key_obj = self._public_key  # Use cached property

            if isinstance(public_key_obj, ec.EllipticCurvePublicKey):
                # Use compressed format for EC keys, standard for Bitcoin/ETH addresses
                pubkey_bytes = public_key_obj.public_bytes(
                    encoding=Encoding.X962,
                    format=PublicFormat.CompressedPoint
                )
            elif isinstance(public_key_obj, rsa.RSAPublicKey):
                # Use standard DER format for others
                pubkey_bytes = public_key_obj.public_bytes(
                    encoding=Encoding.DER,
                    format=PublicFormat.SubjectPublicKeyInfo
                )
            else:
                raise CryptoError(f"Cannot generate address for unsupported key type: {type(public_key_obj)}")

            # Use CryptoUtils to derive address from the public key bytes
            self._address = CryptoUtils.generate_address_from_public_key(pubkey_bytes)

        return self._address

    def sign(self, message: Union[str, bytes]) -> str:
        """
        Signs a message with the private key. Uses the cached key object for performance.
        """
        if isinstance(message, str):
            message = message.encode('utf-8')

        key = self._private_key  # Use cached property

        if isinstance(key, rsa.RSAPrivateKey):
            signature = key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        elif isinstance(key, ec.EllipticCurvePrivateKey):
            signature = key.sign(
                message,
                ec.ECDSA(hashes.SHA256())
            )
        else:
            # This should be unreachable if constructor validation is correct
            raise CryptoError(f"Unsupported key type for signing: {type(key)}")

        return base64.b64encode(signature).decode('utf-8')

    def verify(self, message: Union[str, bytes], signature: str) -> bool:
        """
        Verifies a signature with the public key. Uses the cached key object for performance.
        """
        if isinstance(message, str):
            message = message.encode('utf-8')

        try:
            signature_bytes = base64.b64decode(signature)
            key = self._public_key  # Use cached property

            if isinstance(key, ec.EllipticCurvePublicKey):
                key.verify(
                    signature_bytes,
                    message,
                    ec.ECDSA(hashes.SHA256())
                )
            elif isinstance(key, rsa.RSAPublicKey):
                key.verify(
                    signature_bytes,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
            else:
                # This should be unreachable
                raise CryptoError(f"Unsupported key type for verification: {type(key)}")
            return True
        except InvalidSignature:
            # This is an expected failure case (bad signature)
            logger.debug("Signature verification failed.")
            return False
        except Exception as e:
            # Any other exception is unexpected
            logger.error(f"An unexpected error occurred during verification: {e}")
            return False

    def to_dict(self) -> Dict[str, str]:
        """Converts the KeyPair to a dictionary representation."""
        return {
            'private_key_pem': self.private_key_pem,
            'public_key_pem': self.public_key_pem,
            'address': self.get_address(),
            'key_type': self.key_type
        }

    @classmethod
    def from_dict(cls, key_dict: Dict[str, str]) -> 'KeyPair':
        """Creates a KeyPair from a dictionary representation."""
        if 'private_key_pem' not in key_dict or 'public_key_pem' not in key_dict:
            raise ValueError("Key dictionary missing required 'private_key_pem' or 'public_key_pem' fields.")
        return cls(
            private_key_pem=key_dict['private_key_pem'],
            public_key_pem=key_dict['public_key_pem'],
            address=key_dict.get('address'),
            key_type=key_dict.get('key_type')
        )
