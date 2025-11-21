#!/usr/bin/env python3
"""validator_index_service.py -- for validator management with logic in validator_helper."""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from BachiCoin.lib_validator.validator_config import (
    ValidatorStatus,
    is_valid_validator_status,
)
from BachiCoin.lib_validator.validator_storage_adapter import ValidatorStorageAdapter
from BachiCoin.lib_user.user_index_service import UserIndexService
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_mempool.mempool_index_service import MempoolIndexService
from BachiCoin.lib_transaction.tx_config import TxType
from BachiCoin.lib_validator import validator_helper


class ValidatorIndexService:
    """Manages the validator index, state, and lifecycle operations."""

    def __init__(self, storage_adapter: ValidatorStorageAdapter, user_index_service: UserIndexService,
                 wallet_index_service: WalletIndexService):
        """Initializes the service with all dependencies injected."""
        self.storage = storage_adapter
        self.user_index_service = user_index_service
        self.wallet_index_service = wallet_index_service
        self._ensure_validator_index_exists()

    # =================== INDEX ===================

    def _ensure_validator_index_exists(self) -> None:
        index = self.storage.load_validator_index()
        if not index or "metadata" not in index or "by_user" not in index:
            initial_index = {
                "validators": {},
                "by_pubkey": {},
                "by_user": {},
                "metadata": {
                    "total_validators": 0,
                    "genesis_timestamp": int(datetime.now().timestamp()),
                    "last_updated": datetime.now().isoformat() + "Z",
                },
            }
            assert self.storage.save_validator_index(initial_index)

    def _get_next_validator_index(self) -> int:
        index = self.storage.load_validator_index()
        return index["metadata"]["total_validators"]

    # =================== LOOKUPS ===================

    def find_validator_by_pubkey(self, pubkey: str) -> Optional[Dict[str, Any]]:
        index = self.storage.load_validator_index()
        idx = index["by_pubkey"].get(pubkey)
        return self.storage.load_validator(idx) if idx is not None else None

    def find_validator_by_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        index = self.storage.load_validator_index()
        idx = index["by_user"].get(user_id)
        return self.storage.load_validator(idx) if idx is not None else None

    # =================== LIFECYCLE ===================

    def register_validator(self, user_id: str, wallet_id: str, withdrawal_credentials: str = None) -> Optional[int]:
        # Check if user is already a validator
        existing_validator = self.find_validator_by_user(user_id)
        if existing_validator:
            print(f"User {user_id} is already a validator. Returning existing validator index.")
            return existing_validator.get("validator_index")

        user_data = self.user_index_service.get_user_summary(user_id)
        assert user_data, f"User {user_id} not found"

        wallet_data = self.wallet_index_service.get_wallet(wallet_id)
        assert wallet_data, f"Wallet {wallet_id} not found"
        assert wallet_data.get("user_id") == user_id

        # Removed: assert not self.find_validator_by_user(user_id), f"User {user_id} is already a validator"

        validator_index = self._get_next_validator_index()
        pubkey = validator_helper.extract_validator_pubkey(wallet_data)

        if not withdrawal_credentials:
            eoa_address = wallet_data.get("addresses", {}).get("eoa", {}).get("address", "")
            assert eoa_address, f"No EOA address in wallet {wallet_id}"
            withdrawal_credentials = "0x01" + "00" * 11 + eoa_address[2:]

        validator_data = validator_helper.create_genesis_validator_data(validator_index, pubkey, withdrawal_credentials)
        validator_data["user_id"] = user_id

        assert self.storage.save_validator(validator_index, validator_data)

        def update_func(index_data): return validator_helper.add_validator_to_index(index_data, validator_data, user_id)

        assert self.storage.update_validator_index(update_func)

        return validator_index

    def update_validator_status(self, validator_index: int, new_status: str) -> bool:
        assert is_valid_validator_status(new_status)

        def update_func(v: Dict[str, Any]) -> Dict[str, Any]:
            v["status"] = new_status
            v["updated_at"] = datetime.now().isoformat() + "Z"
            return v

        updated = self.storage.update_validator(validator_index, update_func)
        if updated:
            def ufunc(index_data): return validator_helper.update_validator_in_index(index_data, updated)

            self.storage.update_validator_index(ufunc)
        return updated is not None

    # =================== TX OPS ===================

    def get_pending_txs(self, mempool_index_service: MempoolIndexService, limit: int = None) -> List[Dict[str, Any]]:
        return mempool_index_service.get_pending_transactions(limit)

    def filter_valid_txs(self, tx_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        TX_TYPE_PRIORITY = {
            TxType.MINT.value: 0,
            TxType.BURN.value: 1,
            TxType.TRANSFER.value: 2,
            TxType.STAKE.value: 3,
            TxType.UNSTAKE.value: 4,
            TxType.REWARD.value: 5,
            TxType.SLASH.value: 6,
            TxType.CONTRACT_CALL.value: 7,
            TxType.CONTRACT_DEPLOY.value: 8,
            TxType.GOVERNANCE.value: 9,
        }
        DEFAULT_PRIORITY = 99

        def sort_key(tx: Dict[str, Any]) -> tuple:
            tx_type = tx.get("tx_type", TxType.TRANSFER.value)
            type_priority = TX_TYPE_PRIORITY.get(tx_type, DEFAULT_PRIORITY)
            priority_fee = tx.get("max_priority_fee_per_gas", 0.0)
            tx_size = len(json.dumps(tx, sort_keys=True).encode("utf-8"))
            return (type_priority, -priority_fee, tx_size)

        return sorted(tx_list, key=sort_key)

    # =================== QUERIES ===================

    def get_validator(self, validator_index: int) -> Optional[Dict[str, Any]]:
        return self.storage.load_validator(validator_index)

    def get_active_validators(self) -> List[int]:
        index = self.storage.load_validator_index()
        return sorted(
            int(idx) for idx, val in index.get("validators", {}).items()
            if val.get("status") == ValidatorStatus.ACTIVE_ONGOING.value
        )

    def get_validator_summary(self) -> Dict[str, Any]:
        return validator_helper.summarize_validators(self.storage.load_validator_index())

    def get_validator_counts(self) -> Dict[str, int]:
        summary = self.get_validator_summary()
        return {
            "total_validators": summary["total_validators"],
            "active_validators": summary["by_status"].get(ValidatorStatus.ACTIVE_ONGOING.value, 0),
        }

    def close(self) -> None:
        self.storage.close()


if __name__ == '__main__':
    print("--- Smoke Test for ValidatorIndexService.filter_valid_txs ---")

    # Mock dependencies
    class MockValidatorStorageAdapter(ValidatorStorageAdapter):
        def __init__(self, base_path=None): self._data = {}; super().__init__(None)
        def load_validator_index(self): return {"validators": {}, "by_pubkey": {}, "by_user": {}, "metadata": {"total_validators": 0}}
        def save_validator_index(self, data): self._data['index'] = data; return True
        def load_validator(self, idx): return None
        def save_validator(self, idx, data): return True
        def update_validator(self, idx, func): return None
        def close(self): pass

    class MockUserIndexService:
        pass

    class MockWalletIndexService:
        pass

    # 1. Setup
    storage = MockValidatorStorageAdapter()
    user_service = MockUserIndexService()
    wallet_service = MockWalletIndexService()
    validator_service = ValidatorIndexService(storage, user_service, wallet_service)
    print("   Service initialized.")

    # 2. Create sample transactions with different types and priorities
    tx_mint = {"tx_type": TxType.MINT.value, "max_priority_fee_per_gas": 10.0, "amount": 100, "chain_id": 1, "gas_limit": 21000, "to_address": "0x1", "data": "0x", "access_list": [], "from_address": None, "nonce": None}
    tx_transfer_high_fee = {"tx_type": TxType.TRANSFER.value, "max_priority_fee_per_gas": 5.0, "amount": 10, "chain_id": 1, "gas_limit": 21000, "from_address": "0x2", "to_address": "0x3", "nonce": 0, "data": "0x", "access_list": []}
    tx_burn = {"tx_type": TxType.BURN.value, "max_priority_fee_per_gas": 2.0, "amount": 50, "chain_id": 1, "gas_limit": 21000, "from_address": "0x4", "nonce": 0, "data": "0x", "access_list": [], "to_address": None}
    tx_transfer_low_fee = {"tx_type": TxType.TRANSFER.value, "max_priority_fee_per_gas": 1.0, "amount": 5, "chain_id": 1, "gas_limit": 21000, "from_address": "0x5", "to_address": "0x6", "nonce": 0, "data": "0x", "access_list": []}
    tx_stake = {"tx_type": TxType.STAKE.value, "max_priority_fee_per_gas": 3.0, "amount": 32, "chain_id": 1, "gas_limit": 100000, "from_address": "0x7", "nonce": 0, "data": "0x", "access_list": []}

    unsorted_txs = [
        tx_transfer_high_fee,
        tx_burn,
        tx_mint,
        tx_transfer_low_fee,
        tx_stake,
    ]

    # 3. Filter and sort transactions
    print("\n3. Testing filter_valid_txs sorting...")
    sorted_txs = validator_service.filter_valid_txs(unsorted_txs)

    # Expected order based on TX_TYPE_PRIORITY and then -priority_fee
    # MINT (0), BURN (1), TRANSFER (2, high fee), TRANSFER (2, low fee), STAKE (3)
    expected_order = [
        tx_mint,
        tx_burn,
        tx_transfer_high_fee,
        tx_transfer_low_fee,
        tx_stake,
    ]

    # Compare sorted list with expected order
    assert len(sorted_txs) == len(expected_order), "Sorted list length mismatch."
    for i, tx in enumerate(sorted_txs):
        assert tx["tx_type"] == expected_order[i]["tx_type"],\
            f"Mismatch at index {i}: Expected {expected_order[i]['tx_type']}, Got {tx['tx_type']}"
        if tx["tx_type"] == TxType.TRANSFER.value:
            # For transfers, check priority fee as well
            assert tx["max_priority_fee_per_gas"] == expected_order[i]["max_priority_fee_per_gas"],\
                f"Mismatch at index {i} for {tx['tx_type']}: Expected fee {expected_order[i]['max_priority_fee_per_gas']}, Got {tx['max_priority_fee_per_gas']}"
    print("   PASS: Transactions sorted correctly by type priority and fee.")

    print("\n--- Smoke Test Passed ---")
