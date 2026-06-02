import struct
import os
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def generate_keypair():
    """Generates ECDSA secp256k1 key pair."""
    private_key = ec.generate_private_key(ec.SECP256K1())
    public_key = private_key.public_key()
    return private_key, public_key

def sha256(data: bytes) -> bytes:
    """Computes SHA-256 hash."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update(data)
    return digest.finalize()

def ecdsa_sign(private_key, digest: bytes) -> bytes:
    """Signs digest using ECDSA (prehashed)."""
    signature = private_key.sign(
        digest,
        ec.ECDSA(utils.Prehashed(hashes.SHA256()))
    )
    return signature

def ecdsa_verify(public_key, digest: bytes, signature: bytes) -> bool:
    """Verifies ECDSA signature."""
    try:
        public_key.verify(
            signature,
            digest,
            ec.ECDSA(utils.Prehashed(hashes.SHA256()))
        )
        return True
    except Exception:
        return False

def aes_encrypt(key: bytes, plaintext: bytes) -> bytes:
    """Encrypts plaintext using AES-256-GCM. Prepends 12-byte random nonce."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext

def aes_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    """Decrypts ciphertext using AES-256-GCM."""
    aesgcm = AESGCM(key)
    nonce = ciphertext[:12]
    data = ciphertext[12:]
    return aesgcm.decrypt(nonce, data, None)

def canonical_serialize(fields: list) -> bytes:
    """Deterministic length-prefixed serialization (network byte order)."""
    serialized = bytearray()
    for field in fields:
        if isinstance(field, str):
            field_bytes = field.encode('utf-8')
        elif isinstance(field, bytes):
            field_bytes = field
        elif isinstance(field, int):
            # Assuming 8-byte ints for serialization
            field_bytes = struct.pack(">q", field)
        elif isinstance(field, float):
            # 8-byte float
            field_bytes = struct.pack(">d", field)
        else:
            raise ValueError(f"Unsupported type {type(field)}")
        
        # Length prefixed 4 bytes
        serialized.extend(struct.pack(">I", len(field_bytes)))
        serialized.extend(field_bytes)
    return bytes(serialized)
