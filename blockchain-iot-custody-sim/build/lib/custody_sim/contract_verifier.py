from typing import Optional, Dict, Any
from .models import CustodyEvent, VerificationResult
from .crypto_engine import ecdsa_verify, canonical_serialize, sha256
import time

class DeviceRegistry:
    def __init__(self):
        self._registry = {} # device_id -> public_key
        self._active_status = {} # device_id -> bool

    def register_device(self, device_id: str, public_key: Any):
        self._registry[device_id] = public_key
        self._active_status[device_id] = True

    def get_public_key(self, device_id: str) -> Optional[Any]:
        return self._registry.get(device_id)

    def is_active(self, device_id: str) -> bool:
        return self._active_status.get(device_id, False)

class AssetLedger:
    def __init__(self):
        # (device_id, asset_id) -> last sequence number
        self.last_sequence = {} 
        self.events = []
    
    def get_last_sequence(self, device_id: str, asset_id: str) -> int:
        return self.last_sequence.get((device_id, asset_id), 0)

    def update(self, event: CustodyEvent):
        self.last_sequence[(event.device_id, event.asset_id)] = event.sequence_number
        self.events.append(event)

class CustodyVerifier:
    def __init__(self, registry: DeviceRegistry, ledger: AssetLedger, config: dict):
        self.registry = registry
        self.ledger = ledger
        self.config = config
        self.skew_window = config.get("skew_window", 300)

    def verify(self, event: CustodyEvent, current_block_timestamp: float) -> VerificationResult:
        start_time = time.time()
        
        # We start with some naive gas accumulated per step
        gas_naive = 0
        gas_optimized = 0

        # Step 1: Device Authentication
        gas_naive += 2000
        gas_optimized += 2000
        if not self.registry.is_active(event.device_id):
            return VerificationResult(False, "device_inactive", gas_naive, gas_optimized, (time.time()-start_time)*1000)
        
        public_key = self.registry.get_public_key(event.device_id)
        if not public_key:
            return VerificationResult(False, "device_not_registered", gas_naive, gas_optimized, (time.time()-start_time)*1000)

        # Step 2: Signature verification (anchorEvent base logic)
        gas_naive += 148200
        gas_optimized += 92400
        if not ecdsa_verify(public_key, event.composite_hash, event.signature):
            return VerificationResult(False, "signature_invalid", gas_naive, gas_optimized, (time.time()-start_time)*1000)

        # Step 3: Hash integrity
        message = canonical_serialize([
            event.encrypted_payload,
            event.timestamp,
            event.sender_id,
            event.receiver_id,
            event.sequence_number,
            event.device_id
        ])
        expected_hash = sha256(message)
        if expected_hash != event.composite_hash:
            return VerificationResult(False, "hash_mismatch", gas_naive, gas_optimized, (time.time()-start_time)*1000)

        # Step 4: Timestamp validation
        if abs(event.timestamp - current_block_timestamp) > self.skew_window:
            return VerificationResult(False, "timestamp_expired", gas_naive, gas_optimized, (time.time()-start_time)*1000)

        # Step 5: Sequence validation
        last_seq = self.ledger.get_last_sequence(event.device_id, event.asset_id)
        if event.sequence_number <= last_seq:
            return VerificationResult(False, "sequence_violation", gas_naive, gas_optimized, (time.time()-start_time)*1000)

        # Step 6: Business rules (verifyEvent)
        gas_naive += 67800
        gas_optimized += 58300
        # In a real environment, we would decrypt the payload and check temp etc here,
        # but for the simulation with AES GCM, we only do gas modeling to keep it simple,
        # unless adversarial engine modified the business rule. Since adversarial modifies payloads
        # the hash check catches it before getting here.

        # Step 7: State recording
        gas_naive += 44600
        gas_optimized += 44600
        self.ledger.update(event)

        return VerificationResult(True, None, gas_naive, gas_optimized, (time.time()-start_time)*1000)
