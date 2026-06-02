from dataclasses import dataclass
from typing import Optional, List

@dataclass
class CustodyEvent:
    event_id: str              # UUID
    asset_id: str              # Parcel identifier
    device_id: str             # IoT seal device ID
    sender_id: str             # Transferring party
    receiver_id: str           # Receiving party
    timestamp: float           # Unix timestamp (ms precision)
    sequence_number: int       # Monotonically increasing per (device, asset)
    encrypted_payload: bytes   # AES-256-GCM encrypted telemetry
    composite_hash: bytes      # SHA-256(encrypted_payload || timestamp || context)
    signature: bytes           # ECDSA signature over composite_hash
    is_adversarial: bool       # Ground truth label
    attack_type: Optional[str] # None if legitimate

@dataclass
class VerificationResult:
    success: bool
    failure_reason: Optional[str]  
    # None if success; else one of:
    # 'device_not_registered', 'device_inactive', 'signature_invalid',
    # 'hash_mismatch', 'timestamp_expired', 'sequence_violation',
    # 'business_rule_temperature', 'business_rule_geofence',
    # 'business_rule_actor_sequence'
    gas_used_naive: int
    gas_used_optimized: int
    verification_time_ms: float

@dataclass
class BlockchainBlock:
    block_number: int
    timestamp: float
    base_fee_gwei: float
    transactions: List[CustodyEvent]
    gas_used: int
    gas_limit: int
    config_name: str  # 'ethereum', 'layer2', 'high_throughput'
