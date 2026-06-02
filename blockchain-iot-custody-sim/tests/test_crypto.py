import pytest
from custody_sim.crypto_engine import generate_keypair, sha256, ecdsa_sign, ecdsa_verify, canonical_serialize

def test_t001_crypto_primitives():
    priv, pub = generate_keypair()
    msg = b"hello test"
    digest = sha256(msg)
    sig = ecdsa_sign(priv, digest)
    assert ecdsa_verify(pub, digest, sig) == True

def test_t002_canonical_serialization_determinism():
    fields1 = [b"enc_data", 1682000000.0, "senderA", "recvB", 1, "dev1"]
    fields2 = [b"enc_data", 1682000000.0, "senderA", "recvB", 1, "dev1"]
    assert canonical_serialize(fields1) == canonical_serialize(fields2)
