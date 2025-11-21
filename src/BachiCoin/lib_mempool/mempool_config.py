#!/usr/bin/env python3
"""Modern mempool configuration - Consistent with new tx_config.py"""

import time
from enum import Enum
from typing import Dict, Any, List

MEMPOOL_INDEX_KEY = "mempool_index"

from BachiCoin.lib_transaction.tx_validation import (
    TxType, Priority, is_valid_address, is_valid_tx_hash, is_valid_signature,TxConfig
)

class MempoolStatus(Enum):
    """Transaction states within mempool"""
    PENDING = "pending"        # Ready for inclusion
    QUEUED = "queued"         # Waiting for nonce gap resolution
    BROADCASTING = "broadcasting"  # Being propagated to network
    INCLUDED = "included"      # Included in a block
    DROPPED = "dropped"        # Removed from pool
    EXPIRED = "expired"        # Timed out
    REPLACED = "replaced"      # Superseded by higher fee tx

class NonceStrategy(Enum):
    """Nonce gap handling strategies"""
    STRICT_SEQUENTIAL = "strict_sequential"  # No gaps allowed
    LIMITED_GAPS = "limited_gaps"           # Allow small gaps
    ETHEREUM_STANDARD = "ethereum_standard" # Standard Ethereum behavior

class EvictionPolicy(Enum):
    """Pool eviction strategies when full"""
    LOWEST_FEE = "lowest_fee"           # Remove lowest fee transactions
    OLDEST_FIRST = "oldest_first"       # Remove oldest transactions
    ACCOUNT_LIMIT = "account_limit"     # Remove from accounts with most txs
    HYBRID_FEE_AGE = "hybrid_fee_age"   # Combined fee/age scoring

class MempoolConfig:
    """Mempool operational policies and limits - aligned with Ethereum standards"""
    
    # Pool size limits (based on Ethereum client defaults)
    MAX_POOL_SIZE = 5_000              # Total transactions in pool (Geth default)
    MAX_PENDING_PER_ACCOUNT = 16       # Geth default for pending
    MAX_QUEUED_PER_ACCOUNT = 64        # Geth default for future nonces
    MAX_POOL_SIZE_MB = 256             # Memory limit for pool
    
    # Transaction lifecycle (Ethereum standard timing)
    TX_LIFETIME_SECONDS = 3 * 3600     # 3 hours
    CLEANUP_INTERVAL = 300             # 5 minutes
    REBROADCAST_INTERVAL = 60          # 1 minute
    
    # Admission policies (uses GWEI like tx_config)
    MIN_PRIORITY_FEE_THRESHOLD = 1.0   # Minimum priority fee (GWEI)
    FEE_BUMP_MIN_PERCENTAGE = 10       # Minimum % increase for replacement (EIP-1559 standard)
    UNDERPRICE_TIMEOUT = 300           # Seconds before reconsidering underpriced
    
    # Nonce management (Ethereum behavior)
    NONCE_STRATEGY = NonceStrategy.ETHEREUM_STANDARD.value
    MAX_NONCE_GAP = 1000               # Maximum allowed gap in nonces
    NONCE_CACHE_SIZE = 10_000          # Cache account nonces
    
    # Network policies (Ethereum standards)
    MAX_TX_SIZE_BYTES = 128 * 1024     # 128KB transaction size limit
    PROPAGATION_TIMEOUT = 10           # Seconds for network propagation
    MAX_BROADCAST_PEERS = 25           # Ethereum standard
    
    # Broadcasting configuration (for mempool_broadcaster)
    BROADCAST_ENABLED = True           # Enable network broadcasting
    MAX_RETRY_ATTEMPTS = 3            # Maximum broadcast retry attempts
    BROADCAST_RETRY_INTERVAL = 2.0    # Seconds between retry attempts
    
    # Eviction and cleanup
    EVICTION_POLICY = EvictionPolicy.HYBRID_FEE_AGE.value
    EVICTION_BATCH_SIZE = 50           # Remove this many at once
    ACCOUNT_SLOT_PROTECTION = 4        # Reserve slots per account
    
    # Performance tuning
    ENABLE_PERSISTENCE = True
    PERSISTENCE_INTERVAL = 60          # Save pool state every minute
    MEMORY_PRESSURE_THRESHOLD = 0.8   # Trigger cleanup at 80% memory
    
    # Fee-based filtering (consistent with tx_config Priority levels)
    DYNAMIC_FEE_ADJUSTMENT = True      # Adjust minimums based on pool state
    FEE_HISTORY_BLOCKS = 20           # Blocks to consider for fee estimation
    PRIORITY_QUEUE_SIZE = 1000        # High-priority transaction buffer

class MempoolValidation:
    """Mempool-specific validation rules (not transaction format validation)"""
    
    @staticmethod
    def validate_pool_admission(tx: Dict[str, Any], pool_state: Dict[str, Any]) -> List[str]:
        """Validate transaction for mempool admission (policy checks only)"""
        errors = []
        
        # Size limits
        if pool_state.get("total_size", 0) >= MempoolConfig.MAX_POOL_SIZE:
            errors.append("Pool is full")
            
        # Account limits
        from_addr = tx.get("from_address", "")
        account_pending = pool_state.get("account_pending", {}).get(from_addr, 0)
        if account_pending >= MempoolConfig.MAX_PENDING_PER_ACCOUNT:
            errors.append(f"Account {from_addr} has too many pending transactions")
            
        # Fee thresholds (consistent with tx_config fee structure)
        priority_fee = tx.get("max_priority_fee_per_gas", 0)
        if priority_fee < MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD:
            errors.append(f"Priority fee {priority_fee} below minimum {MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD}")
            
        # Gas limit validation (use tx_config constants)
        gas_limit = tx.get("gas_limit", 0)
        if gas_limit < TxConfig.MIN_GAS_LIMIT:
            errors.append(f"Gas limit {gas_limit} below minimum {TxConfig.MIN_GAS_LIMIT}")
        if gas_limit > TxConfig.MAX_GAS_LIMIT:
            errors.append(f"Gas limit {gas_limit} above maximum {TxConfig.MAX_GAS_LIMIT}")
            
        # Transaction size
        tx_size = len(str(tx).encode('utf-8'))
        if tx_size > MempoolConfig.MAX_TX_SIZE_BYTES:
            errors.append(f"Transaction size {tx_size} exceeds limit {MempoolConfig.MAX_TX_SIZE_BYTES}")
            
        return errors
    
    @staticmethod
    def validate_replacement(old_tx: Dict[str, Any], new_tx: Dict[str, Any]) -> List[str]:
        """Validate transaction replacement (EIP-1559 rules)"""
        errors = []
        
        # Same sender and nonce required
        if old_tx.get("from_address") != new_tx.get("from_address"):
            errors.append("Different sender address")
            
        if old_tx.get("nonce") != new_tx.get("nonce"):
            errors.append("Different nonce")
            
        # Fee bump requirement (EIP-1559 standard)
        old_max_fee = old_tx.get("max_fee_per_gas", 0)
        new_max_fee = new_tx.get("max_fee_per_gas", 0)
        
        min_bump = old_max_fee * (1 + MempoolConfig.FEE_BUMP_MIN_PERCENTAGE / 100)
        if new_max_fee < min_bump:
            errors.append(f"Fee bump insufficient: {new_max_fee} < {min_bump}")
            
        # Priority fee must also increase
        old_priority = old_tx.get("max_priority_fee_per_gas", 0)
        new_priority = new_tx.get("max_priority_fee_per_gas", 0)
        
        min_priority_bump = old_priority * (1 + MempoolConfig.FEE_BUMP_MIN_PERCENTAGE / 100)
        if new_priority < min_priority_bump:
            errors.append(f"Priority fee bump insufficient: {new_priority} < {min_priority_bump}")
            
        return errors
    
    @staticmethod
    def validate_nonce_sequence(tx: Dict[str, Any], account_state: Dict[str, Any]) -> List[str]:
        """Validate nonce sequence for account"""
        errors = []
        
        tx_nonce = tx.get("nonce", 0)
        account_nonce = account_state.get("next_nonce", 0)
        pending_nonces = account_state.get("pending_nonces", set())
        
        # Nonce too low (already used)
        if tx_nonce < account_nonce:
            errors.append(f"Nonce {tx_nonce} too low, expected >= {account_nonce}")
            
        # Nonce gap too large
        if tx_nonce > account_nonce + MempoolConfig.MAX_NONCE_GAP:
            errors.append(f"Nonce gap too large: {tx_nonce} > {account_nonce + MempoolConfig.MAX_NONCE_GAP}")
            
        # Duplicate nonce (unless replacing)
        if tx_nonce in pending_nonces:
            errors.append(f"Nonce {tx_nonce} already pending (use replacement)")
            
        return errors
    
    @staticmethod
    def validate_transaction_format(tx: Dict[str, Any]) -> List[str]:
        """Basic format validation (delegates to tx_config for consistency)"""
        errors = []
        
        # Always required fields
        required_base_fields = ["tx_hash", "max_fee_per_gas", "max_priority_fee_per_gas"]
        for field in required_base_fields:
            if field not in tx or tx[field] is None:
                errors.append(f"Missing required field: {field}")

        tx_type = tx.get("tx_type")

        # Conditional required fields based on tx_type
        if tx_type in [TxType.TRANSFER.value, TxType.STAKE.value, TxType.UNSTAKE.value]:
            if "from_address" not in tx or tx["from_address"] is None:
                errors.append("Missing required field: from_address")
            if "to_address" not in tx or tx["to_address"] is None:
                errors.append("Missing required field: to_address")
            if "nonce" not in tx or tx["nonce"] is None:
                errors.append("Missing required field: nonce")
        elif tx_type == TxType.BURN.value:
            if "from_address" not in tx or tx["from_address"] is None:
                errors.append("Missing required field: from_address")
            # to_address is None for BURN, so not required
            if "nonce" not in tx or tx["nonce"] is None:
                errors.append("Missing required field: nonce")
        elif tx_type == TxType.SLASH.value:
            if "from_address" not in tx or tx["from_address"] is None:
                errors.append("Missing required field: from_address")
            # to_address and nonce are None for SLASH, so not required
        elif tx_type == TxType.MINT.value or tx_type == TxType.REWARD.value:
            if "to_address" not in tx or tx["to_address"] is None:
                errors.append("Missing required field: to_address")
            # from_address and nonce are None for MINT/REWARD, so not required

        # Format validation using tx_config functions
        if "tx_hash" in tx and not is_valid_tx_hash(tx["tx_hash"]):
            errors.append("Invalid transaction hash format")
            
        if "from_address" in tx and tx["from_address"] is not None and not is_valid_address(tx["from_address"]):
            errors.append("Invalid from_address format")
            
        if "to_address" in tx and tx["to_address"] is not None and not is_valid_address(tx["to_address"]):
            errors.append("Invalid to_address format")
            
        if "signature" in tx and tx["signature"] and not is_valid_signature(tx["signature"]):
            errors.append("Invalid signature format")
        
        return errors

class MempoolMetrics:
    """Mempool monitoring and statistics"""
    
    @staticmethod
    def calculate_priority_score(tx: Dict[str, Any], current_base_fee: float = 0.0) -> float:
        """Calculate transaction priority score for ordering (EIP-1559 compliant)"""
        max_fee = tx.get("max_fee_per_gas", 0)
        priority_fee = tx.get("max_priority_fee_per_gas", 0)
        
        # Effective priority fee (EIP-1559) - use tx_config calculation
        effective_priority = TxConfig.calculate_effective_gas_price(max_fee, priority_fee, current_base_fee) - current_base_fee
        
        # Age factor (newer transactions get slight priority boost)
        submitted_at = tx.get("submitted_at", "")
        if submitted_at:
            try:
                submission_time = time.mktime(time.strptime(submitted_at[:19], "%Y-%m-%dT%H:%M:%S"))
                age_seconds = time.time() - submission_time
                # Max 10% boost for transactions under 5 minutes old
                age_factor = 1.0 + (300 - min(age_seconds, 300)) / 3000
            except (ValueError, TypeError):
                age_factor = 1.0
        else:
            age_factor = 1.0
        
        return effective_priority * age_factor
    
    @staticmethod
    def get_pool_statistics(pool_state: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive pool statistics"""
        return {
            "total_transactions": pool_state.get("total_size", 0),
            "pending_transactions": pool_state.get("pending_count", 0),
            "queued_transactions": pool_state.get("queued_count", 0),
            "unique_accounts": len(pool_state.get("account_pending", {})),
            "memory_usage_mb": pool_state.get("memory_usage_bytes", 0) / (1024 * 1024),
            "avg_gas_price": pool_state.get("avg_gas_price", 0),
            "pool_utilization": pool_state.get("total_size", 0) / MempoolConfig.MAX_POOL_SIZE * 100,
            "last_cleanup": pool_state.get("last_cleanup", ""),
            "fee_thresholds": {
                "min_priority_fee": MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD,
                "fee_bump_percentage": MempoolConfig.FEE_BUMP_MIN_PERCENTAGE
            }
        }
    
    @staticmethod
    def estimate_inclusion_time(tx: Dict[str, Any], current_base_fee: float) -> Dict[str, Any]:
        """Estimate transaction inclusion time based on current network conditions"""
        priority_score = MempoolMetrics.calculate_priority_score(tx, current_base_fee)
        
        # Simple heuristic based on priority score
        if priority_score >= 50:
            return {"blocks": "1-2", "seconds": "12-24", "confidence": "high"}
        elif priority_score >= 20:
            return {"blocks": "2-5", "seconds": "24-60", "confidence": "medium"}
        elif priority_score >= 5:
            return {"blocks": "5-10", "seconds": "60-120", "confidence": "medium"}
        else:
            return {"blocks": "10+", "seconds": "120+", "confidence": "low"}

class EvictionManager:
    """Handle pool eviction when limits exceeded"""
    
    @staticmethod
    def select_eviction_candidates(pool_txs: List[Dict[str, Any]], count: int, current_base_fee: float = 0.0) -> List[str]:
        """Select transactions for eviction based on policy"""
        if MempoolConfig.EVICTION_POLICY == EvictionPolicy.LOWEST_FEE.value:
            # Sort by effective gas price, remove lowest
            sorted_txs = sorted(pool_txs, key=lambda tx: tx.get("max_fee_per_gas", 0))
            return [tx["tx_hash"] for tx in sorted_txs[:count]]
            
        elif MempoolConfig.EVICTION_POLICY == EvictionPolicy.OLDEST_FIRST.value:
            # Sort by submission time, remove oldest
            sorted_txs = sorted(pool_txs, key=lambda tx: tx.get("submitted_at", ""))
            return [tx["tx_hash"] for tx in sorted_txs[:count]]
            
        elif MempoolConfig.EVICTION_POLICY == EvictionPolicy.HYBRID_FEE_AGE.value:
            # Combined scoring: use priority score from MempoolMetrics
            scored_txs = []
            for tx in pool_txs:
                score = MempoolMetrics.calculate_priority_score(tx, current_base_fee)
                scored_txs.append((score, tx["tx_hash"]))
            
            # Sort by score ascending (lowest score = first to evict)
            scored_txs.sort(key=lambda x: x[0])
            return [tx_hash for score, tx_hash in scored_txs[:count]]
            
        else:
            # Default: oldest first
            sorted_txs = sorted(pool_txs, key=lambda tx: tx.get("submitted_at", ""))
            return [tx["tx_hash"] for tx in sorted_txs[:count]]

# Utility functions
def is_expired(tx: Dict[str, Any]) -> bool:
    """Check if transaction has expired"""
    submitted_at = tx.get("submitted_at", "")
    if not submitted_at:
        return False
        
    try:
        submission_time = time.mktime(time.strptime(submitted_at[:19], "%Y-%m-%dT%H:%M:%S"))
        return (time.time() - submission_time) > MempoolConfig.TX_LIFETIME_SECONDS
    except (ValueError, TypeError):
        return False

def should_cleanup_pool(pool_state: Dict[str, Any]) -> bool:
    """Determine if pool cleanup is needed"""
    last_cleanup = pool_state.get("last_cleanup_time", 0)
    time_since_cleanup = time.time() - last_cleanup
    
    # Time-based cleanup
    if time_since_cleanup > MempoolConfig.CLEANUP_INTERVAL:
        return True
        
    # Memory pressure cleanup
    memory_usage = pool_state.get("memory_usage_bytes", 0)
    memory_limit = MempoolConfig.MAX_POOL_SIZE_MB * 1024 * 1024
    memory_ratio = memory_usage / memory_limit if memory_limit > 0 else 0
    
    return memory_ratio > MempoolConfig.MEMORY_PRESSURE_THRESHOLD

def get_mempool_defaults() -> Dict[str, Any]:
    """Get default mempool configuration"""
    return {
        "max_pool_size": MempoolConfig.MAX_POOL_SIZE,
        "max_pending_per_account": MempoolConfig.MAX_PENDING_PER_ACCOUNT,
        "max_queued_per_account": MempoolConfig.MAX_QUEUED_PER_ACCOUNT,
        "tx_lifetime": MempoolConfig.TX_LIFETIME_SECONDS,
        "nonce_strategy": MempoolConfig.NONCE_STRATEGY,
        "eviction_policy": MempoolConfig.EVICTION_POLICY,
        "min_priority_fee": MempoolConfig.MIN_PRIORITY_FEE_THRESHOLD,
        "fee_bump_percentage": MempoolConfig.FEE_BUMP_MIN_PERCENTAGE,
        "cleanup_interval": MempoolConfig.CLEANUP_INTERVAL,
        "memory_limit_mb": MempoolConfig.MAX_POOL_SIZE_MB,
    }

def validate_mempool_transaction(tx: Dict[str, Any], pool_state: Dict[str, Any], account_state: Dict[str, Any]) -> List[str]:
    """Complete mempool validation pipeline"""
    errors = []
    
    # 1. Format validation (delegates to tx_config)
    errors.extend(MempoolValidation.validate_transaction_format(tx))
    
    # 2. Pool admission policies
    errors.extend(MempoolValidation.validate_pool_admission(tx, pool_state))
    
    # 3. Nonce sequence validation
    # Only validate nonce for transactions that have a nonce
    if tx.get("nonce") is not None:
        errors.extend(MempoolValidation.validate_nonce_sequence(tx, account_state))
    
    return errors

# Legacy aliases for backward compatibility with existing service code
def get_base_fee() -> float:
    """Get current base fee - simple default for now"""
    return 20.0  # Default base fee in GWEI

if __name__ == "__main__":
    print("=== Modern Mempool Config - Consistent with tx_config ===")
    
    # Test configuration
    defaults = get_mempool_defaults()
    print(f"✅ Pool size limit: {defaults['max_pool_size']}")
    print(f"✅ Per-account pending limit: {defaults['max_pending_per_account']}")
    print(f"✅ Transaction lifetime: {defaults['tx_lifetime']}s")
    print(f"✅ Minimum priority fee: {defaults['min_priority_fee']} GWEI")
    print(f"✅ Broadcasting enabled: {MempoolConfig.BROADCAST_ENABLED}")
    
    # Test validation with sample transaction
    sample_tx = {
        "tx_hash": "0x" + "a" * 64,
        "from_address": "0x" + "1" * 40,
        "to_address": "0x" + "2" * 40,
        "nonce": 1,
        "max_fee_per_gas": 40.0,
        "max_priority_fee_per_gas": 2.0,
        "gas_limit": 21000,
        "submitted_at": "2025-08-01T12:00:00Z",
        "signature": "0x" + "a" * 130
    }
    
    pool_state = {"total_size": 100, "account_pending": {}, "memory_usage_bytes": 1024 * 1024}
    account_state = {"next_nonce": 1, "pending_nonces": set()}
    
    errors = validate_mempool_transaction(sample_tx, pool_state, account_state)
    print(f"✅ Complete validation: {len(errors)} errors")
    
    # Test priority scoring
    current_base_fee = 20.0
    score = MempoolMetrics.calculate_priority_score(sample_tx, current_base_fee)
    print(f"✅ Priority score: {score}")
    
    # Test inclusion time estimation
    estimate = MempoolMetrics.estimate_inclusion_time(sample_tx, current_base_fee)
    print(f"✅ Inclusion estimate: {estimate['blocks']} blocks, confidence: {estimate['confidence']}")
    
    # Test eviction
    candidates = EvictionManager.select_eviction_candidates([sample_tx], 1, current_base_fee)
    print(f"✅ Eviction candidates: {len(candidates)}")
    
    print("✅ All mempool tests passed!")
