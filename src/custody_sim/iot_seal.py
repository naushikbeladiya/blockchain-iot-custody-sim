import json
import time
import random
import uuid
from .crypto_engine import aes_encrypt, canonical_serialize, sha256, ecdsa_sign
from .models import CustodyEvent

class IoTSeal:
    def __init__(self, device_id: str, private_key, public_key, session_key: bytes):
        self.device_id = device_id
        self.private_key = private_key
        self.public_key = public_key
        self.session_key = session_key

    def generate_telemetry(self) -> dict:
        """Generates random telemetry data for the simulation."""
        # Simple random telemetry as per PRD
        temperature = random.uniform(2.0, 8.0) 
        humidity = random.uniform(30.0, 70.0)
        shock = random.uniform(0.0, 1.5)
        lat = random.uniform(33.0, 34.0)
        lon = random.uniform(-118.0, -117.0)
        
        return {
            "temperature": temperature,
            "humidity": humidity,
            "shock_g": shock,
            "gps": {"lat": lat, "lon": lon}
        }

    def encrypt_payload(self, telemetry: dict) -> bytes:
        """AES-256-GCM encryption of JSON-serialized telemetry."""
        plaintext = json.dumps(telemetry).encode('utf-8')
        return aes_encrypt(self.session_key, plaintext)

    def construct_message(self, encrypted_payload: bytes, timestamp: float, sender_id: str, receiver_id: str, seq_num: int) -> bytes:
        """Canonical length-prefixed serialization."""
        fields = [
            encrypted_payload,
            timestamp,
            sender_id,
            receiver_id,
            seq_num,
            self.device_id
        ]
        return canonical_serialize(fields)

    def compute_hash(self, message: bytes) -> bytes:
        """SHA-256 of canonical byte sequence."""
        return sha256(message)

    def sign_hash(self, digest: bytes) -> bytes:
        """ECDSA signature over secp256k1 using device's private key."""
        return ecdsa_sign(self.private_key, digest)

    def create_handoff_event(self, asset_id: str, sender_id: str, receiver_id: str, sequence_number: int, sim_time: float) -> CustodyEvent:
        """Orchestrates standard handoff workflow and returns CustodyEvent."""
        telemetry = self.generate_telemetry()
        encrypted_payload = self.encrypt_payload(telemetry)
        # We use sim_time as timestamp (in real life, device has RTC)
        timestamp = sim_time
        
        message = self.construct_message(
            encrypted_payload=encrypted_payload,
            timestamp=timestamp,
            sender_id=sender_id,
            receiver_id=receiver_id,
            seq_num=sequence_number
        )
        
        digest = self.compute_hash(message)
        signature = self.sign_hash(digest)
        
        event = CustodyEvent(
            event_id=str(uuid.uuid4()),
            asset_id=asset_id,
            device_id=self.device_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            timestamp=timestamp, # milliseconds normally or seconds, PRD asks for ms or seconds check (we use ms or seconds, skew is 300s so timestamp is likely seconds)
            sequence_number=sequence_number,
            encrypted_payload=encrypted_payload,
            composite_hash=digest,
            signature=signature,
            is_adversarial=False,
            attack_type=None
        )
        return event
