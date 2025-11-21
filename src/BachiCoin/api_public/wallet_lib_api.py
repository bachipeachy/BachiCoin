#!/usr/bin/env python3
"""wallet_lib_api.py It ensures all interactions are properly orchestrated through the service layer."""

from typing import Dict, Any, List, Optional

# Import services and factories
from BachiCoin.lib_wallet.wallet_index_service import WalletIndexService
from BachiCoin.lib_wallet.wallet_helper import adjust_wallet_balance as _adjust_wallet_balance
from BachiCoin.lib_wallet.wallet_service_factory import WalletServiceFactory
from BachiCoin.lib_crossmodule.node_context import adapt_context_arg
from BachiCoin.lib_wallet.wallet_config import WalletType as _WalletType

WalletType = _WalletType

from BachiCoin.lib_wallet.system_wallets import create_system_wallets as _create_system_wallets

def create_wallet_index_service(*args, **kwargs) -> WalletIndexService:
    """
    Creates WalletIndexService by delegating to the WalletServiceFactory.
    Accepts either a Dirs object or a NodeContext object.
    """
    return adapt_context_arg(WalletServiceFactory.create_wallet_index_service, *args, **kwargs)

def create_wallet_with_index(
        service: WalletIndexService,
        user_id: str,
        wallet_data: Dict[str, Any],
        addresses: Dict[str, Any] # The full dictionary of derived addresses
) -> Optional[str]:
    """Creates a new wallet, including its cryptographic keys and index entry."""
    return service.create_wallet_with_index(user_id, wallet_data, addresses)

def delete_wallet_with_index(service: WalletIndexService, wallet_id: str) -> bool:
    """Deletes a wallet record and its index entry."""
    return service.delete_wallet_with_index(wallet_id)

def list_wallets(service: WalletIndexService, wallet_type: str = None, status: str = None,
                 user_id: str = None) -> List[Dict[str, Any]]:
    """List wallets with filters"""
    return service.list_wallets(wallet_type, status, user_id)

def get_wallet_summary(service: WalletIndexService, wallet_id: str) -> Optional[Dict[str, Any]]:
    """Gets a wallet's summary data (from the index for speed)."""
    return service.get_wallet_summary(wallet_id)

def get_wallet(service: WalletIndexService, wallet_id: str) -> Optional[Dict[str, Any]]:
    """Gets a wallet's full data record, including sensitive fields."""
    return service.get_wallet(wallet_id)

def get_wallet_data(service: WalletIndexService, wallet_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_wallet for API consistency."""
    return service.get_wallet(wallet_id)

def list_wallets_by_user(service: WalletIndexService, user_id: str) -> List[Dict[str, Any]]:
    """Lists all wallet summaries for a given user."""
    return service.list_wallets_by_user(user_id)

def get_wallet_id_by_address(service: WalletIndexService, address: str) -> Optional[str]:
    """Retrieves a wallet ID by a specific address."""
    return service.get_wallet_id_by_address(address)

def update_wallet(service: WalletIndexService, wallet_id: str, update_data: Dict[str, Any]) -> bool:
    """Updates a wallet's general data fields."""
    return service.update_wallet(wallet_id, update_data)

def update_wallet_balance(service: WalletIndexService, wallet_id: str, new_balance: float) -> bool:
    """Updates a wallet's balance in both the main record and the index.
    NOTE: This sets the balance to an absolute value, it does not add/subtract.
    """
    return service.update_account_state(wallet_id, balance=new_balance)

def reconcile_user_balance(service: WalletIndexService, user_id: str) -> bool:
    """Calculates a user's total balance by summing their wallets and updates the user record."""
    return service.reconcile_user_balance(user_id)

def search_wallets(service: WalletIndexService, query: str) -> List[Dict[str, Any]]:
    """Searches for wallets by a query string."""
    return service.search_wallets(query)

def get_wallet_stats(service: WalletIndexService) -> Dict[str, Any]:
    """Gets statistics about all wallets in the index."""
    return service.get_wallet_stats()

def rebuild_wallet_index(service: WalletIndexService) -> Dict[str, Any]:
    """Rebuilds the wallet index from the source data files."""
    return service.rebuild_wallet_index()

def adjust_wallet_balance(service: WalletIndexService, wallet_id: str, amount_delta: float) -> bool:
    return _adjust_wallet_balance(service, wallet_id, amount_delta)

def create_system_wallets(wallet_service: WalletIndexService, system_user_ids: Dict[str, str]) -> Dict[str, str]:
    """High-level wrapper to create the standard system wallets."""
    return _create_system_wallets(wallet_service, system_user_ids)


if __name__ == "__main__":
    print("--- Wallet API Smoke Test (Currently Disabled) ---")
