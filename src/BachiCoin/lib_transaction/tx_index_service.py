#!/usr/bin/env python3
"""Transaction Index Service – clean KISS version with only 'txs' key."""
from typing import Dict, Any, Optional, List
from datetime import datetime

from BachiCoin.lib_transaction.tx_validation import TxValidation
from BachiCoin.lib_transaction.tx_helper import (
    apply_tx_defaults,
    populate_jit_fields,
    build_index_entry,
    parse_iso8601,
)
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_transaction.tx_storage_adapter import TxStorageAdapter
from BachiCoin.lib_transaction.tx_config import get_tx_schema_view, TxType


class TxIndexService:
    """Service for creating, validating, and indexing transactions."""

    def __init__(self, storage_adapter: TxStorageAdapter, wallet_index_service: Optional[WalletIndexService] = None):
        assert isinstance(storage_adapter, TxStorageAdapter)
        # Allow wallet_index_service to be None for smoke tests where it's not directly used.
        if wallet_index_service is not None:
            assert isinstance(wallet_index_service, WalletIndexService)
        self.storage = storage_adapter
        self.wallet_index_service = wallet_index_service

    # ------------------------------------------------------
    # Transaction lifecycle
    # ------------------------------------------------------
    def create_tx_with_index(
        self,
        tx_data: Dict[str, Any],
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
        calculated_nonce: Optional[int] = None,
        override_nonce: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Prepares a transaction object with defaults and JIT fields, but does not sign or save it."""
        tx_payload = tx_data.copy()

        # Explicitly set from_address, to_address, and nonce in tx_payload.
        # This ensures they are always present, even if their value is None.
        # apply_tx_defaults will then see these keys and not try to add defaults like "".
        tx_payload["from_address"] = from_address
        tx_payload["to_address"] = to_address

        if override_nonce is not None:
            tx_payload["nonce"] = override_nonce
        elif calculated_nonce is not None:
            tx_payload["nonce"] = calculated_nonce
        else:
            tx_payload["nonce"] = None # Explicitly set to None if no nonce is provided

        tx = apply_tx_defaults(tx_payload)
        tx = populate_jit_fields(tx)
        return tx

    def save_signed_transaction(self, signed_tx: Dict[str, Any]) -> bool:
        """Validates, saves, and indexes a signed transaction."""
        errors = TxValidation.validate_transaction(signed_tx)
        if errors:
            raise ValueError(f"Transaction validation failed: {errors}")

        tx_hash = signed_tx.get("tx_hash")
        if not tx_hash:
            raise ValueError("Signed transaction must have a tx_hash.")

        if not self.storage.save_tx(tx_hash, signed_tx):
            return False
        
        return self.create_index_entry(signed_tx)

    def update_transaction(self, tx_hash: str, update_data: Dict[str, Any]) -> bool:
        """Update a transaction record and its index entry."""
        tx_data = self.storage.load_tx(tx_hash)
        if not tx_data:
            return False

        tx_data.update(update_data)
        tx_data["last_modified"] = datetime.now().isoformat() + "Z"
        if not self.storage.save_tx(tx_hash, tx_data):
            return False

        index_fields = get_tx_schema_view("index").keys()
        index_changes = {k: v for k, v in update_data.items() if k in index_fields}
        if index_changes:
            return self.update_index_entry(tx_hash, index_changes)
        return True

    # ------------------------------------------------------
    # Index handling
    # ------------------------------------------------------
    def create_index_entry(self, tx_data: Dict[str, Any]) -> bool:
        entry = build_index_entry(tx_data)
        index_data = self.storage.load_index_data() or {"txs": {}}
        index_data["txs"][tx_data["tx_hash"]] = entry
        return self.storage.save_index_data(index_data)

    def update_index_entry(self, tx_hash: str, changes: Dict[str, Any]) -> bool:
        index_data = self.storage.load_index_data() or {"txs": {}}
        assert tx_hash in index_data["txs"], f"Transaction {tx_hash} not found in index"

        for field, value in changes.items():
            errors = TxValidation.validate_field(field, value)
            assert not errors, f"Invalid field {field}: {errors}"
            index_data["txs"][tx_hash][field] = value

        return self.storage.save_index_data(index_data)

    def list_transactions(
        self,
        tx_type: Optional[str] = None,
        currency: Optional[str] = None,
        from_address: Optional[str] = None,
        to_address: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        index_data = self.storage.load_index_data() or {"txs": {}}
        txs = index_data.get("txs", {})
        results = []
        for tx_hash, tx_info in txs.items():
            if tx_type and tx_info.get("tx_type") != tx_type:
                continue
            if currency and tx_info.get("currency") != currency:
                continue
            if from_address and tx_info.get("from_address") != from_address:
                continue
            if to_address and tx_info.get("to_address") != to_address:
                continue
            results.append({"tx_hash": tx_hash, **tx_info})
        return results

    def search_transactions(self, query: str) -> List[Dict[str, Any]]:
        if not query:
            return []
        query_lower = query.lower()
        index_data = self.storage.load_index_data() or {"txs": {}}
        transactions = index_data.get("txs", {})
        results = []
        for tx_hash, tx_info in transactions.items():
            searchable = " ".join(str(tx_info.get(f, "")) for f in
                ["memo", "from_address", "to_address", "tx_type", "amount", "currency"]).lower()
            if query_lower in searchable or query_lower in tx_hash.lower():
                results.append({"tx_hash": tx_hash, **tx_info})
        return results

    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        return self.storage.load_tx(tx_hash)

    def delete_transaction(self, tx_hash: str) -> bool:
        if not self.storage.delete_tx(tx_hash):
            return False
        index_data = self.storage.load_index_data() or {"txs": {}}
        index_data["txs"].pop(tx_hash, None)
        return self.storage.save_index_data(index_data)

    # ------------------------------------------------------
    # Analytics
    # ------------------------------------------------------
    def get_tx_index_stats(self) -> Dict[str, Any]:
        index_data = self.storage.load_index_data() or {"txs": {}}
        transactions = index_data.get("txs", {})
        stats = {"total_transactions": len(transactions), "by_type": {}, "by_currency": {}, "total_amount": 0.0, "total_fees": 0.0}
        for tx_info in transactions.values():
            ttype = tx_info.get("tx_type", "unknown")
            stats["by_type"][ttype] = stats["by_type"].get(ttype, 0) + 1
            currency = tx_info.get("currency", "unknown")
            stats["by_currency"][currency] = stats["by_currency"].get(currency, 0) + 1
            stats["total_amount"] += float(tx_info.get("amount", 0.0))
            stats["total_fees"] += float(tx_info.get("total_fee", 0.0))
        return stats

    def get_transactions_by_address(self, address: str) -> Dict[str, Any]:
        sent = self.list_transactions(from_address=address)
        received = self.list_transactions(to_address=address)
        return {"sent": sent, "received": received, "total_sent": len(sent), "total_received": len(received)}

    def sort_transactions_by_timestamp(self, txs: List[Dict[str, Any]], reverse: bool = False) -> List[Dict[str, Any]]:
        return sorted(txs, key=lambda tx: parse_iso8601(tx.get("timestamp", "")), reverse=reverse)

    def rebuild_index_from_records(self) -> Dict[str, Any]:
        all_tx_hashes = self.storage.list_tx_hashes()
        rebuilt_index = {"txs": {}}
        processed, errors = 0, 0
        for tx_hash in all_tx_hashes:
            tx_data = self.storage.load_tx(tx_hash)
            if tx_data and "tx_hash" in tx_data:
                rebuilt_index["txs"][tx_hash] = build_index_entry(tx_data)
                processed += 1
            else:
                errors += 1
        success = self.storage.save_index_data(rebuilt_index)
        return {"success": success, "processed": processed, "errors": errors, "total_keys": len(all_tx_hashes)}

    def close(self) -> None:
        if hasattr(self.storage, "close") and callable(self.storage.close):
            self.storage.close()

if __name__ == '__main__':
    print("--- Smoke Test for TxIndexService ---")

    # Mock dependencies
    class MockStorageAdapter(TxStorageAdapter):
        def __init__(self, base_path=None):
            self._data = {}
        def save_tx(self, tx_hash, tx_data): self._data[tx_hash] = tx_data; return True
        def load_tx(self, tx_hash): return self._data.get(tx_hash)
        def list_tx_hashes(self): return list(self._data.keys())
        def delete_tx(self, tx_hash): return self._data.pop(tx_hash, None) is not None
        def save_index_data(self, data): self._data['index'] = data; return True
        def load_index_data(self): return self._data.get('index')
        def close(self): pass

    # 1. Setup
    storage = MockStorageAdapter()
    tx_service = TxIndexService(storage, wallet_index_service=None) # Pass None for the dependency
    print("   Service initialized.")

    from_addr = "0x" + "a" * 40
    to_addr = "0x" + "b" * 40
    dummy_nonce = 5

    # 2. Test create_tx_with_index for a TRANSFER
    print("\n2. Testing create_tx_with_index for 'transfer'...")
    transfer_tx_data = {
        "tx_type": TxType.TRANSFER.value,
        "amount": 1.23
    }
    unsigned_transfer_tx = tx_service.create_tx_with_index(
        transfer_tx_data,
        from_address=from_addr,
        to_address=to_addr,
        calculated_nonce=dummy_nonce
    )
    assert unsigned_transfer_tx["nonce"] == dummy_nonce
    assert unsigned_transfer_tx["from_address"] == from_addr
    assert unsigned_transfer_tx["to_address"] == to_addr
    assert unsigned_transfer_tx["gas_limit"] == 21000  # Default
    print("   PASS: create_tx_with_index for 'transfer' successful.")

    # 3. Test create_tx_with_index for a MINT
    print("\n3. Testing create_tx_with_index for 'mint'...")
    mint_tx_data = {
        "tx_type": TxType.MINT.value,
        "amount": 1000
    }
    unsigned_mint_tx = tx_service.create_tx_with_index(
        mint_tx_data,
        from_address=None, # Explicitly pass None
        to_address=to_addr, 
        calculated_nonce=None # Explicitly pass None
    )
    assert unsigned_mint_tx["to_address"] == to_addr
    assert unsigned_mint_tx["from_address"] is None 
    assert unsigned_mint_tx["nonce"] is None 
    print("   PASS: create_tx_with_index for 'mint' successful.")

    # 4. Test create_tx_with_index for a BURN
    print("\n4. Testing create_tx_with_index for 'burn'...")
    burn_tx_data = {
        "tx_type": TxType.BURN.value,
        "amount": 500
    }
    unsigned_burn_tx = tx_service.create_tx_with_index(
        burn_tx_data,
        from_address=from_addr, 
        to_address=None, # Explicitly pass None
        calculated_nonce=dummy_nonce 
    )
    assert unsigned_burn_tx["from_address"] == from_addr
    assert unsigned_burn_tx["to_address"] is None 
    assert unsigned_burn_tx["nonce"] == dummy_nonce
    print("   PASS: create_tx_with_index for 'burn' successful.")

    print("\n--- Smoke Test Passed ---")
