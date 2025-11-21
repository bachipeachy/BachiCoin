#!/usr/bin/env python3
"""Modern blockchain configuration - EIP-1559 aligned with Bitcoin hybrid support"""

import re
import time
import json
from enum import Enum
from typing import Dict, List, Any

from BachiCoin.lib_crypto.crypto_utils import CryptoUtils

BLOCKCHAIN_INDEX_KEY = "blockchain_index"

BLOCKCHAIN_SCHEMA_VERSION = 1  # EIP-1559 + Bitcoin hybrid support

# JIT_FIELDS: dynamic, computed when building / importing block
JIT_FIELDS = [
    "block_hash",          # Calculated from block header
    "transactions_root",   # Merkle root of txs
    "receipts_root",       # Merkle root of receipts
    "state_root",          # Verkle root after execution
    "transaction_count",   # len(transactions)
    "gas_used",            # sum of tx gas_used (EIP-1559)
    "total_fees",          # sum of tx total_fee (EIP-1559)
    "timestamp",           # set if missing at creation
    "created_at",          # when block built
    "last_modified",       # updated on modification
    "received_at",         # set when received by node
    "validated_at",        # set when validated
    "block_size",          # serialized size
]

# Configuration constants (ETH + Bitcoin hybrid)
MAX_TIMESTAMP_DRIFT = 15  # seconds into future (Ethereum-style)
MAX_GAS_LIMIT_CHANGE = 1024  # 1/1024 max change between ETH blocks

# Block types and status
class BlockType(Enum):
    GENESIS = "genesis"
    REGULAR = "regular"
    UNCLE = "uncle"          # Ethereum-style uncle blocks
    CHECKPOINT = "checkpoint"
    # Bitcoin hybrid support
    MERGE_MINED = "merge_mined"  # Bitcoin merge-mined block

class BlockStatus(Enum):
    PROPOSED   = "proposed"     # Block built and gossiped, awaiting justification
    JUSTIFIED  = "justified"    # Passed 2/3 attestation threshold; canonical, state executed
    FINALIZED  = "finalized"    # Fully locked, cannot be reverted
    INVALID    = "invalid"      # Failed validation or slashed proposer
    ORPHANED   = "orphaned"     # Valid but lost fork choice, not in canonical chain

class NetworkType(Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    REGTEST = "regtest"
    DEVNET = "devnet"

class ConsensusType(Enum):
    """Consensus mechanisms for hybrid support"""
    PROOF_OF_STAKE = "proof_of_stake"    # ETH2 PoS (primary)
    PROOF_OF_WORK = "proof_of_work"      # Bitcoin PoW (hybrid support)
    HYBRID = "hybrid"                    # Combined PoS + PoW

class BlockchainConfig:
    """Modern blockchain configuration - EIP-1559 + Bitcoin hybrid ready"""
    
    # ID Patterns
    BLOCK_HASH_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')
    MERKLE_ROOT_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')
    VERKLE_ROOT_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')
    
    # Block constraints
    MAX_BLOCK_SIZE_BYTES = 2_000_000      # 2MB byte guardrail
    MAX_GAS_LIMIT = 30_000_000            # 30M gas limit
    MIN_GAS_LIMIT = 5_000_000             # 5M gas minimum
    MAX_EXTRA_DATA_SIZE = 256             # 256 bytes extra data
    
    # EIP-1559 gas and fees
    BASE_FEE_MAX_CHANGE_DENOMINATOR = 8   # Max 12.5% base fee change
    ELASTICITY_MULTIPLIER = 2             # Gas target = limit / 2
    MIN_BASE_FEE = 1_000_000_000          # 1 Gwei minimum
    
    # Bitcoin hybrid: Difficulty adjustment
    DIFFICULTY_ADJUSTMENT_PERIOD = 2016   # Bitcoin-style period
    MIN_DIFFICULTY = 1
    MAX_DIFFICULTY = 2**256 - 1
    
    # Defaults
    DEFAULT_NETWORK = NetworkType.TESTNET.value
    DEFAULT_BLOCK_TYPE = BlockType.REGULAR.value
    DEFAULT_STATUS = BlockStatus.PROPOSED.value
    DEFAULT_GAS_LIMIT = 15_000_000        # 15M gas default
    DEFAULT_CONSENSUS = ConsensusType.PROOF_OF_STAKE.value
    
    def __init__(self):
        pass

    # Master Block Schema - EIP-1559 + Bitcoin hybrid
    _BLOCK_MASTER_SCHEMA = {
        # === Header: identity & parent link ===
        "block_hash": {"type": str, "required": True, "immutable": True, "format": "block_hash"},
        "parent_hash": {"type": str, "required": True, "immutable": True, "format": "block_hash"},
        "height": {"type": int, "required": True, "immutable": True, "min_value": 0},

        # === ETH2 consensus slot & epoch ===
        "slot": {"type": int, "required": True, "min_value": 0},
        "epoch": {"type": int, "required": True, "min_value": 0},

        # === Proposer identity & randomness ===
        "proposer_index": {"type": int, "required": True, "min_value": 0},
        "randao_reveal": {"type": str, "required": False, "format": "hex_string"},

        # === State commitments (Verkle/Merkle roots) ===
        "state_root": {"type": str, "required": True, "format": "verkle_root"},
        "transactions_root": {"type": str, "required": True, "format": "merkle_root"},
        "receipts_root": {"type": str, "required": True, "format": "merkle_root"},

        # === EIP-1559 gas & fee accounting ===
        "gas_limit": {"type": int, "required": True, "min_value": MIN_GAS_LIMIT, "max_value": MAX_GAS_LIMIT, "default": DEFAULT_GAS_LIMIT},
        "gas_used": {"type": int, "required": True, "min_value": 0, "default": 0},
        "base_fee_per_gas": {"type": int, "required": True, "min_value": MIN_BASE_FEE, "default": MIN_BASE_FEE},

        # === Bitcoin hybrid: PoW fields (future-proofing) ===
        "difficulty": {"type": int, "required": False, "min_value": MIN_DIFFICULTY},
        "nonce": {"type": int, "required": False, "min_value": 0},
        "mix_hash": {"type": str, "required": False, "format": "block_hash"},
        "bits": {"type": str, "required": False},  # Bitcoin difficulty target
        "chainwork": {"type": str, "required": False},  # Bitcoin cumulative work

        # === Consensus type ===
        "consensus_type": {"type": str, "required": True, "default": DEFAULT_CONSENSUS,
                          "allowed_values": [ct.value for ct in ConsensusType]},

        # === Timing & metadata ===
        "timestamp": {"type": int, "required": True, "min_value": 0},
        "extra_data": {"type": bytes, "required": False, "max_length": MAX_EXTRA_DATA_SIZE, "default": b""},

        # === Classification ===
        "block_type": {"type": str, "required": True, "default": BlockType.REGULAR.value,
                       "allowed_values": [bt.value for bt in BlockType]},
        "network": {"type": str, "required": True, "default": NetworkType.TESTNET.value,
                    "allowed_values": [nt.value for nt in NetworkType]},

        # === Body: transactions & consensus operations ===
        "transactions": {"type": list, "required": True, "default": []},
        "transaction_count": {"type": int, "required": True, "min_value": 0, "default": 0},

        # ETH2: attestations & slashings (optional)
        "attestations": {"type": list, "required": False, "default": []},
        "proposer_slashings": {"type": list, "required": False, "default": []},
        "attester_slashings": {"type": list, "required": False, "default": []},

        # Bitcoin hybrid: uncle blocks (optional)
        "uncle_headers": {"type": list, "required": False, "default": []},

        # === EIP-1559 computed metrics ===
        "total_fees": {"type": float, "required": False, "min_value": 0, "default": 0.0},
        "block_size": {"type": int, "required": False, "min_value": 0, "default": 0},
        "bloom_filter": {"type": str, "required": False, "format": "hex_string"},

        # === Status: chain state & finality ===
        "status": {"type": str, "required": True, "default": BlockStatus.PROPOSED.value,
                   "allowed_values": [bs.value for bs in BlockStatus]},
        "is_canonical": {"type": bool, "required": False, "default": False},

        # Finality epochs
        "justified_epoch": {"type": int, "required": False, "min_value": 0},
        "finalized_epoch": {"type": int, "required": False, "min_value": 0},

        # Bitcoin hybrid: total difficulty / cumulative gas
        "total_difficulty": {"type": int, "required": False, "min_value": 0, "default": 0},
        "cumulative_gas_used": {"type": int, "required": False, "min_value": 0, "default": 0},

        # Timing / audit fields
        "received_at": {"type": str, "required": False, "format": "iso8601"},
        "validated_at": {"type": str, "required": False, "format": "iso8601"},
        "created_at": {"type": str, "required": False, "format": "iso8601"},
        "last_modified": {"type": str, "required": False, "format": "iso8601"},
    }

    # Schema views for different operations
    BLOCK_SCHEMA_VIEWS: Dict[str, List[str]] = {
        "full_schema": list(_BLOCK_MASTER_SCHEMA.keys()),
        "create": ["parent_hash", "height", "slot", "epoch", "proposer_index", "randao_reveal",
                   "transactions", "gas_limit", "base_fee_per_gas", "timestamp", "extra_data", 
                   "block_type", "network", "consensus_type"],
        "mining": ["parent_hash", "state_root", "transactions_root", "receipts_root",
                   "gas_limit", "gas_used", "base_fee_per_gas", "timestamp", "extra_data", 
                   "nonce", "mix_hash", "slot", "epoch", "proposer_index", "difficulty", "bits"],
        "validation": ["block_hash", "parent_hash", "height", "slot", "epoch", "proposer_index",
                       "state_root", "transactions_root", "receipts_root", "gas_limit", "gas_used", 
                       "base_fee_per_gas", "timestamp", "transactions", "transaction_count", "consensus_type"],
        "index": ["parent_hash", "height", "slot", "epoch", "block_type", "network", "status",
                  "timestamp", "gas_limit", "gas_used", "base_fee_per_gas", "is_canonical", 
                  "justified_epoch", "finalized_epoch", "consensus_type"],
        "consensus": ["slot", "epoch", "proposer_index", "randao_reveal", "attestations", 
                      "proposer_slashings", "attester_slashings", "justified_epoch", "finalized_epoch"],
        "storage": list(_BLOCK_MASTER_SCHEMA.keys()),
        "network": ["block_hash", "parent_hash", "height", "slot", "epoch", "state_root", 
                    "transactions_root", "receipts_root", "gas_limit", "gas_used", "base_fee_per_gas", 
                    "timestamp", "extra_data", "transactions", "attestations", "consensus_type"],
        # Bitcoin hybrid views
        "pow": ["difficulty", "nonce", "mix_hash", "bits", "chainwork", "total_difficulty"],
        "hybrid": ["consensus_type", "difficulty", "nonce", "slot", "epoch", "proposer_index"]
    }

    # Default configurations for different block types
    BLOCK_TYPE_DEFAULTS = {
        BlockType.GENESIS.value: {
            "parent_hash": "0x" + "0" * 64,
            "height": 0,
            "slot": 0,
            "epoch": 0,
            "proposer_index": 0,
            "difficulty": MIN_DIFFICULTY,
            "base_fee_per_gas": MIN_BASE_FEE,
            "gas_limit": DEFAULT_GAS_LIMIT,
            "timestamp": 0,
            "extra_data": b"BachiCoin Genesis Block",
            "status": BlockStatus.FINALIZED.value,
            "consensus_type": ConsensusType.PROOF_OF_STAKE.value
        },
        BlockType.REGULAR.value: {
            "gas_limit": DEFAULT_GAS_LIMIT,
            "base_fee_per_gas": MIN_BASE_FEE,
            "difficulty": MIN_DIFFICULTY,
            "status": BlockStatus.PROPOSED.value,
            "consensus_type": ConsensusType.PROOF_OF_STAKE.value
        },
        BlockType.UNCLE.value: {
            "is_canonical": False,
            "status": BlockStatus.ORPHANED.value
        },
        BlockType.MERGE_MINED.value: {
            "consensus_type": ConsensusType.HYBRID.value,
            "status": BlockStatus.PROPOSED.value
        }
    }

    @classmethod
    def get_required_fields(cls, view: str = None) -> List[str]:
        """Get required fields for view or all"""
        if view:
            schema = get_block_schema_view(view)
        else:
            schema = cls._BLOCK_MASTER_SCHEMA
        return [field for field, config in schema.items() if config.get("required", False)]

    @classmethod
    def get_allowed_values(cls, field_name: str) -> List[Any]:
        """Get allowed values for field"""
        return cls._BLOCK_MASTER_SCHEMA.get(field_name, {}).get("allowed_values", [])

    @classmethod
    def get_field_constraints(cls, field_name: str) -> Dict[str, Any]:
        """Get all constraints for a field"""
        return cls._BLOCK_MASTER_SCHEMA.get(field_name, {})

    @classmethod
    def get_block_type_defaults(cls, block_type: str) -> Dict[str, Any]:
        """Get default configuration for block type"""
        return cls.BLOCK_TYPE_DEFAULTS.get(block_type, {})


# Utility functions (module level)
def get_block_schema_view(view: str) -> Dict[str, Any]:
    """Get schema fields for specific view"""
    assert view in BlockchainConfig.BLOCK_SCHEMA_VIEWS, f"Unknown block schema view: {view}"
    return {k: BlockchainConfig._BLOCK_MASTER_SCHEMA[k] for k in BlockchainConfig.BLOCK_SCHEMA_VIEWS[view]
            if k in BlockchainConfig._BLOCK_MASTER_SCHEMA}

def get_block_defaults_for_view(view: str) -> Dict[str, Any]:
    """Get default values for specific view"""
    schema = get_block_schema_view(view)
    return {field: config.get("default") for field, config in schema.items() 
            if "default" in config}

def get_block_full_defaults() -> Dict[str, Any]:
    """Get full defaults for ALL master schema fields with JIT handling"""
    defaults = {}

    for field, config in BlockchainConfig._BLOCK_MASTER_SCHEMA.items():
        if field in JIT_FIELDS:
            # JIT fields set to None - populated during processing
            defaults[field] = None
        elif "default" in config:
            # Static defaults from schema
            defaults[field] = config["default"]
        else:
            # Fields without defaults set to appropriate empty value
            field_type = config.get("type", str)
            if field_type == str:
                defaults[field] = None  # Use None for optional strings
            elif field_type in (int, float):
                defaults[field] = 0.0 if field_type == float else 0
            elif field_type == dict:
                defaults[field] = {}
            elif field_type == list:
                defaults[field] = []
            else:
                defaults[field] = None

    return defaults

def get_initial_index_structure() -> dict:
    """Returns the default structure for a new blockchain index."""
    return {
        "blocks": {},
        "tx_trie_roots": {},
        "receipt_trie_roots": {},
        "state_trie_roots": {},
        "validators": {},
        "sync_committees": {},
        "chain_state": {
            "chain_tip_hash": None, "chain_height": -1,
            "finalized_hash": None, "finalized_height": -1,
            "safe_hash": None, "safe_height": -1,
            "state_root": None
        }
    }

def is_jit_field(field_name: str) -> bool:
    """Check if field is JIT (Just-In-Time) populated"""
    return field_name in JIT_FIELDS

def get_jit_fields() -> List[str]:
    """Get list of JIT fields"""
    return JIT_FIELDS.copy()

# Validation helper functions
def is_valid_block_hash(block_hash: str) -> bool:
    """Validate block hash format"""
    return bool(BlockchainConfig.BLOCK_HASH_PATTERN.match(block_hash or ""))

def is_valid_merkle_root(merkle_root: str) -> bool:
    """Validate merkle root format"""
    return bool(BlockchainConfig.MERKLE_ROOT_PATTERN.match(merkle_root or ""))

def is_valid_verkle_root(verkle_root: str) -> bool:
    """Validate verkle root format"""
    return bool(BlockchainConfig.VERKLE_ROOT_PATTERN.match(verkle_root or ""))

def is_valid_block_type(block_type: str) -> bool:
    """Validate block type"""
    return block_type in [bt.value for bt in BlockType]

def is_valid_network_type(network: str) -> bool:
    """Validate network type"""
    return network in [nt.value for nt in NetworkType]

def is_valid_block_status(status: str) -> bool:
    """Validate block status"""
    return status in [bs.value for bs in BlockStatus]

def is_valid_consensus_type(consensus: str) -> bool:
    """Validate consensus type"""
    return consensus in [ct.value for ct in ConsensusType]

def calculate_next_base_fee(parent_gas_used: int, parent_gas_limit: int, parent_base_fee: int) -> int:
    """Calculate next block's base fee using EIP-1559 formula"""
    gas_target = parent_gas_limit // BlockchainConfig.ELASTICITY_MULTIPLIER
    
    if parent_gas_used == gas_target:
        return parent_base_fee
    elif parent_gas_used > gas_target:
        # Increase base fee
        gas_used_delta = parent_gas_used - gas_target
        base_fee_delta = max(
            parent_base_fee * gas_used_delta // gas_target // BlockchainConfig.BASE_FEE_MAX_CHANGE_DENOMINATOR,
            1
        )
        return parent_base_fee + base_fee_delta
    else:
        # Decrease base fee
        gas_used_delta = gas_target - parent_gas_used
        base_fee_delta = parent_base_fee * gas_used_delta // gas_target // BlockchainConfig.BASE_FEE_MAX_CHANGE_DENOMINATOR
        return max(parent_base_fee - base_fee_delta, BlockchainConfig.MIN_BASE_FEE)

# =================== EIP-1559 DATA GENERATION UTILITIES ===================

def generate_block_hash(block_data: Dict[str, Any]) -> str:
    """Generate deterministic block hash from block data - EIP-1559 + Bitcoin hybrid"""
    # Create hash input from core block fields - EIP-1559 aligned
    hash_input = {
        "parent_hash": block_data.get("parent_hash", ""),
        "height": block_data.get("height", 0),
        "timestamp": block_data.get("timestamp", int(time.time())),
        "transactions_root": block_data.get("transactions_root", "0x" + "0" * 64),
        "gas_used": block_data.get("gas_used", 0),
        "gas_limit": block_data.get("gas_limit", 15000000),
        "base_fee_per_gas": block_data.get("base_fee_per_gas", 1000000000),
        "extra_data": serialize_extra_data(block_data.get("extra_data", b"")),
        "consensus_type": block_data.get("consensus_type", "proof_of_stake")
    }
    
    # Add Bitcoin hybrid fields if present (future-proofing)
    if block_data.get("consensus_type") in ["proof_of_work", "hybrid"]:
        hash_input["difficulty"] = block_data.get("difficulty", 1)
        hash_input["nonce"] = block_data.get("nonce", 0)

    # Generate deterministic hash using CryptoUtils
    hash_string = json.dumps(hash_input, sort_keys=True, separators=(',', ':'))
    hash_bytes = CryptoUtils.hash_data(hash_string.encode('utf-8'))
    return "0x" + hash_bytes.hex()

def serialize_block_for_json(block_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert block data to JSON-serializable format"""
    serializable = block_data.copy()

    # Handle bytes fields
    if "extra_data" in serializable and isinstance(serializable["extra_data"], bytes):
        serializable["extra_data"] = serializable["extra_data"].hex()

    return serializable

def calculate_gas_used(transactions: List[Dict[str, Any]]) -> int:
    """Calculate total gas used by transactions - EIP-1559 aligned"""
    total_gas = 0
    for tx in transactions:
        # Use gas_used field (execution result) not gas_price (legacy)
        gas_used = tx.get("gas_used", 21000)  # Standard transaction gas
        total_gas += gas_used
    return total_gas

def calculate_total_fees(transactions: List[Dict[str, Any]]) -> float:
    """Calculate total fees from EIP-1559 transactions"""
    total_fees = 0.0
    for tx in transactions:
        # Use EIP-1559 total_fee field (execution result)
        total_fee = tx.get("total_fee", 0.0)
        total_fees += total_fee
    return total_fees

def serialize_extra_data(extra_data: Any) -> str:
    """Serialize extra_data for hash calculation"""
    if isinstance(extra_data, bytes):
        return extra_data.hex()
    elif isinstance(extra_data, str):
        return extra_data
    else:
        return str(extra_data)

# Bitcoin hybrid utilities (future-proofing)
def calculate_difficulty_adjustment(blocks: List[Dict[str, Any]], target_seconds: int = 600) -> int:
    """Calculate Bitcoin-style difficulty adjustment for hybrid blocks"""
    if len(blocks) < 2:
        return BlockchainConfig.MIN_DIFFICULTY
    
    time_taken = blocks[-1]["timestamp"] - blocks[0]["timestamp"]
    expected_time = target_seconds * (len(blocks) - 1)
    
    if time_taken == 0:
        return blocks[-1].get("difficulty", BlockchainConfig.MIN_DIFFICULTY)
    
    # Simple difficulty adjustment
    current_difficulty = blocks[-1].get("difficulty", BlockchainConfig.MIN_DIFFICULTY)
    adjustment_factor = expected_time / time_taken
    
    # Limit adjustment to prevent wild swings
    adjustment_factor = max(0.25, min(4.0, adjustment_factor))
    
    new_difficulty = int(current_difficulty * adjustment_factor)
    return max(BlockchainConfig.MIN_DIFFICULTY, min(BlockchainConfig.MAX_DIFFICULTY, new_difficulty))

def is_hybrid_block(block_data: Dict[str, Any]) -> bool:
    """Check if block uses hybrid consensus"""
    consensus = block_data.get("consensus_type", "proof_of_stake")
    return consensus in ["hybrid", "proof_of_work"]

def get_consensus_fields(consensus_type: str) -> List[str]:
    """Get relevant fields for consensus type"""
    if consensus_type == "proof_of_stake":
        return ["slot", "epoch", "proposer_index", "randao_reveal", "attestations"]
    elif consensus_type == "proof_of_work":
        return ["difficulty", "nonce", "mix_hash", "bits", "chainwork"]
    elif consensus_type == "hybrid":
        return ["slot", "epoch", "proposer_index", "difficulty", "nonce", "mix_hash"]
    else:
        return []

if __name__ == "__main__":
    """Modern configuration testing - EIP-1559 + Bitcoin hybrid"""
    print("=== Modern BlockchainConfig - EIP-1559 + Bitcoin Hybrid ===")
    
    config = BlockchainConfig()
    print(f"Default gas limit: {config.DEFAULT_GAS_LIMIT}")
    print(f"Default consensus: {config.DEFAULT_CONSENSUS}")
    print(f"Schema version: {BLOCKCHAIN_SCHEMA_VERSION}")
    
    # Test schema views
    print(f"\nSchema views: {list(config.BLOCK_SCHEMA_VIEWS.keys())}")
    
    # Test consensus-specific views
    pow_fields = config.BLOCK_SCHEMA_VIEWS["pow"]
    hybrid_fields = config.BLOCK_SCHEMA_VIEWS["hybrid"]
    print(f"PoW fields ({len(pow_fields)}): {pow_fields}")
    print(f"Hybrid fields ({len(hybrid_fields)}): {hybrid_fields}")
    
    # Test validation functions
    validations = [
        ("block_hash", "0x" + "a" * 64, is_valid_block_hash),
        ("merkle_root", "0x" + "b" * 64, is_valid_merkle_root),
        ("verkle_root", "0x" + "c" * 64, is_valid_verkle_root),
        ("block_type", "merge_mined", is_valid_block_type),
        ("consensus", "hybrid", is_valid_consensus_type),
        ("status", "justified", is_valid_block_status)
    ]
    
    print(f"\nValidation tests:")
    for field, value, validator in validations:
        result = validator(value)
        status = "✅" if result else "❌"
        print(f"  {status} {field}: '{value}' -> {result}")

    # Test EIP-1559 fee calculation
    print(f"\nEIP-1559 Base Fee Tests:")
    test_cases = [
        (7_500_000, 15_000_000, 1_000_000_000, "target usage"),
        (15_000_000, 15_000_000, 1_000_000_000, "full blocks"),
        (5_000_000, 15_000_000, 1_000_000_000, "low usage")
    ]
    
    for gas_used, gas_limit, base_fee, description in test_cases:
        next_fee = calculate_next_base_fee(gas_used, gas_limit, base_fee)
        change_pct = ((next_fee - base_fee) / base_fee) * 100
        print(f"  {description}: {base_fee:,} -> {next_fee:,} ({change_pct:+.1f}%)")

    # Test EIP-1559 data generation
    print(f"\nEIP-1559 Data Generation Test:")
    
    # Sample EIP-1559 transactions
    sample_txs = [
        {"gas_used": 21000, "total_fee": 0.000441},  # Simple transfer
        {"gas_used": 150000, "total_fee": 0.00315},  # Contract call
    ]
    
    gas_used = calculate_gas_used(sample_txs)
    total_fees = calculate_total_fees(sample_txs)
    print(f"✅ Gas used calculation: {gas_used}")
    print(f"✅ Total fees calculation: {total_fees}")
    
    # Test PoS block generation
    pos_block = {
        "parent_hash": "0x" + "0" * 64,
        "height": 0,
        "slot": 0,
        "epoch": 0,
        "proposer_index": 0,
        "transactions": sample_txs,
        "gas_limit": 15000000,
        "base_fee_per_gas": 21000000000,
        "consensus_type": "proof_of_stake"
    }
    
    pos_hash = generate_block_hash(pos_block)
    print(f"✅ PoS block hash: {pos_hash[:16]}...")
    
    # Test hybrid block generation
    hybrid_block = pos_block.copy()
    hybrid_block.update({
        "consensus_type": "hybrid",
        "difficulty": 1000,
        "nonce": 42
    })
    
    hybrid_hash = generate_block_hash(hybrid_block)
    print(f"✅ Hybrid block hash: {hybrid_hash[:16]}...")
    
    # Test consensus field selection
    pos_fields = get_consensus_fields("proof_of_stake")
    pow_fields = get_consensus_fields("proof_of_work")
    hybrid_fields = get_consensus_fields("hybrid")
    
    print(f"\nConsensus Fields:")
    print(f"  PoS: {pos_fields}")
    print(f"  PoW: {pow_fields}")
    print(f"  Hybrid: {hybrid_fields}")
    
    # Test hybrid detection
    is_pos_hybrid = is_hybrid_block(pos_block)
    is_hybrid_hybrid = is_hybrid_block(hybrid_block)
    print(f"✅ PoS hybrid check: {is_pos_hybrid}")
    print(f"✅ Hybrid hybrid check: {is_hybrid_hybrid}")
    print(f"✅ EIP-1559 aligned gas and fee calculations")
    print(f"✅ Bitcoin hybrid support for future PoW operations")
