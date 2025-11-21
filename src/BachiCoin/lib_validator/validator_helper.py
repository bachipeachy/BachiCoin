#!/usr/bin/env python3
"""validator_helper.py - Pure functions for validator operations: index maintenance, summaries,"""

from datetime import datetime
from typing import Dict, Any

from BachiCoin.lib_validator.validator_config import ValidatorStatus, ValidatorConfig
from BachiCoin.lib_crypto.crypto_utils import CryptoUtils


# =================== INDEX HELPERS ===================

def add_validator_to_index(index_data: Dict[str, Any], validator_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Adds a validator to the index structures."""
    validator_index = validator_data["validator_index"]
    pubkey = validator_data["pubkey"]

    index_data["validators"][str(validator_index)] = validator_data
    index_data["by_pubkey"][pubkey] = validator_index
    index_data["by_user"][user_id] = validator_index
    index_data["metadata"]["total_validators"] += 1
    index_data["metadata"]["last_updated"] = datetime.now().isoformat() + "Z"
    return index_data


def update_validator_in_index(index_data: Dict[str, Any], validator_data: Dict[str, Any]) -> Dict[str, Any]:
    """Updates a validator summary in the index."""
    validator_index = str(validator_data["validator_index"])
    if validator_index in index_data.get("validators", {}):
        index_data["validators"][validator_index].update(validator_data)
    index_data["metadata"]["last_updated"] = datetime.now().isoformat() + "Z"
    return index_data


# =================== SUMMARIES ===================

def summarize_validators(index: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a summary of validator set from index."""
    summary = {
        "total_validators": 0,
        "by_status": {},
        "total_effective_balance": 0,
        "slashed_count": 0,
    }
    if not index or "metadata" not in index:
        return summary

    summary["total_validators"] = index["metadata"]["total_validators"]
    for validator_data in index.get("validators", {}).values():
        status = validator_data.get("status", "unknown")
        summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        summary["total_effective_balance"] += validator_data.get("effective_balance", 0)
        if validator_data.get("slashed", False):
            summary["slashed_count"] += 1

    return summary


# =================== PUBKEY + GENESIS ===================

def extract_validator_pubkey(wallet_data: Dict[str, Any]) -> str:
    """
    Extracts a validator pubkey from a wallet record.

    This version reads the public key from the wallet's EOA address entry,
    which is persisted in wallet_index.json. It no longer requires a live
    KeyManager instance.

    Returns a deterministic ETH2-style 96-char hex pubkey (0x + 96 hex chars).
    """
    # Prefer the persisted public key in the EOA address
    addresses = wallet_data.get("addresses", {})
    eoa_info = addresses.get("eoa")
    assert eoa_info and "public_key" in eoa_info, (
        f"Wallet data must include an EOA public key: {wallet_data.get('wallet_id')}"
    )

    pubkey_pem = eoa_info["public_key"]
    key_bytes = pubkey_pem.encode()

    # Hash PEM into deterministic validator pubkey (ETH2-style 96-char hex)
    hashed = CryptoUtils.hash_data(key_bytes, algo="sha256")
    return "0x" + hashed.hex()[:96].ljust(96, "0")

def create_genesis_validator_data(validator_index: int, pubkey: str, withdrawal_credentials: str) -> Dict[str, Any]:
    """Constructs ETH2-style genesis validator record."""
    config = ValidatorConfig()
    return {
        "validator_index": validator_index,
        "pubkey": pubkey,
        "withdrawal_credentials": withdrawal_credentials,
        "effective_balance": config.MIN_DEPOSIT_AMOUNT,
        "slashed": False,
        "activation_eligibility_epoch": 0,
        "activation_epoch": 0,
        "exit_epoch": 2**64 - 1,
        "withdrawable_epoch": 2**64 - 1,
        "status": ValidatorStatus.ACTIVE_ONGOING.value,
    }
