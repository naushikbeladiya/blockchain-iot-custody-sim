import numpy as np
import copy
from .models import CustodyEvent
from .crypto_engine import ecdsa_sign, generate_keypair
import random

class AdversarialEngine:
    def __init__(self, config: dict):
        self.injection_rate = config.get("adversarial_rate", 0.10)
        self.rng = np.random.default_rng(config.get("seed", 42))

        # Distribution of attack types based on PRD Table 2: 
        # 1250/5000 = 0.25 payload, 1000/5000 = 0.20 for timestamp, forgery, replay, 750/5000 = 0.15 sequence.
        self.attacks = [
            ("payload_modification", 0.25),
            ("timestamp_manipulation", 0.20),
            ("signature_forgery", 0.20),
            ("replay_attack", 0.20),
            ("sequence_violation", 0.15)
        ]
        self.attack_names = [a[0] for a in self.attacks]
        self.attack_probs = [a[1] for a in self.attacks]

    def modify_payload(self, event: CustodyEvent) -> CustodyEvent:
        """Flips 1-4 bytes in the encrypted_payload while keeping signature and hash unchanged."""
        new_event = copy.deepcopy(event)
        payload_array = bytearray(new_event.encrypted_payload)
        
        num_flips = self.rng.integers(1, 5)
        for _ in range(num_flips):
            idx = self.rng.integers(0, len(payload_array))
            payload_array[idx] ^= 0xFF
            
        new_event.encrypted_payload = bytes(payload_array)
        new_event.is_adversarial = True
        new_event.attack_type = "payload_modification"
        return new_event

    def manipulate_timestamp(self, event: CustodyEvent) -> CustodyEvent:
        """Set timestamp outside the skew window (e.g. ± 600s), preserving original signature."""
        new_event = copy.deepcopy(event)
        # Advance or reverse by 600 seconds
        offset = 600 if self.rng.random() > 0.5 else -600
        new_event.timestamp += offset
        new_event.is_adversarial = True
        new_event.attack_type = "timestamp_manipulation"
        return new_event

    def forge_signature(self, event: CustodyEvent) -> CustodyEvent:
        """New ECDSA signature with unauthorized private key."""
        new_event = copy.deepcopy(event)
        unauth_priv_key, _ = generate_keypair()
        new_event.signature = ecdsa_sign(unauth_priv_key, new_event.composite_hash)
        new_event.is_adversarial = True
        new_event.attack_type = "signature_forgery"
        return new_event

    def replay_event(self, event: CustodyEvent) -> CustodyEvent:
        """Re-submit previously legitimate event with original timestamp/sig."""
        new_event = copy.deepcopy(event)
        new_event.is_adversarial = True
        new_event.attack_type = "replay_attack"
        # Replayed events get exactly the same attributes, 
        # but the simulation submission time will be delayed.
        return new_event

    def violate_sequence(self, event: CustodyEvent) -> CustodyEvent:
        """Submit event with sequence number <= last recorded."""
        new_event = copy.deepcopy(event)
        # We subtract from sequence number to violate monotonically increasing property
        # Make sure it doesn't go below 1
        new_event.sequence_number = max(1, new_event.sequence_number - 1)
        new_event.is_adversarial = True
        new_event.attack_type = "sequence_violation"
        # Re-sign and re-hash so it doesn't fail signature and hash validation
        # Wait, if we change sequence number without re-hashing and re-signing, it fails hash_mismatch.
        # But sequence_violation should be detected at step 5! 
        # So we MUST provide a valid signature and hash for the violated sequence.
        # However, the adversary is the device owner or we simulate a malicious device here.
        # Since we simulate the attack, we can't easily re-sign unless we have the private key.
        # Let's pass private key if we want, or just spoof the verification for this specific mock?
        # Actually, a real device could just sign a lower sequence number.
        return new_event

    def generate_attack(self, event: CustodyEvent, device_private_key=None, attack_type: str = None) -> CustodyEvent:
        if attack_type is None:
            attack_type = self.rng.choice(self.attack_names, p=self.attack_probs)

        if attack_type == "payload_modification":
            return self.modify_payload(event)
        elif attack_type == "timestamp_manipulation":
            return self.manipulate_timestamp(event)
        elif attack_type == "signature_forgery":
            return self.forge_signature(event)
        elif attack_type == "replay_attack":
            return self.replay_event(event)
        elif attack_type == "sequence_violation":
            ev = self.violate_sequence(event)
            if device_private_key:
                from .crypto_engine import canonical_serialize, sha256, ecdsa_sign
                msg = canonical_serialize([
                    ev.encrypted_payload,
                    ev.timestamp,
                    ev.sender_id,
                    ev.receiver_id,
                    ev.sequence_number,
                    ev.device_id
                ])
                ev.composite_hash = sha256(msg)
                ev.signature = ecdsa_sign(device_private_key, ev.composite_hash)
            return ev

        return event


