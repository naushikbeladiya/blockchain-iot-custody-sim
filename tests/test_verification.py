import pytest
from custody_sim.contract_verifier import CustodyVerifier, DeviceRegistry, AssetLedger
from custody_sim.iot_seal import IoTSeal
from custody_sim.crypto_engine import generate_keypair

def test_t003_to_t009_verification_logic():
    # Setup
    reg = DeviceRegistry()
    ledger = AssetLedger()
    verifier = CustodyVerifier(reg, ledger, {"skew_window": 300})
    
    priv, pub = generate_keypair()
    reg.register_device("dev1", pub)
    seal = IoTSeal("dev1", priv, pub, b"sessionk"*4)
    
    # 003 Legitimate event passes
    event = seal.create_handoff_event("asset1", "A", "B", 1, 1000.0)
    res = verifier.verify(event, current_block_timestamp=1000.0)
    assert res.success == True
    
    # 005 Timestamp manipulation (T-005)
    event_ts = seal.create_handoff_event("asset1", "A", "B", 2, 1000.0)
    res_ts = verifier.verify(event_ts, current_block_timestamp=1500.0)
    assert res_ts.success == False
    assert res_ts.failure_reason == "timestamp_expired"
    
    # 006 Signature forgery (T-006)
    event_forge = seal.create_handoff_event("asset1", "A", "B", 3, 1000.0)
    bad_priv, _ = generate_keypair()
    from custody_sim.crypto_engine import ecdsa_sign
    event_forge.signature = ecdsa_sign(bad_priv, event_forge.composite_hash)
    res_forge = verifier.verify(event_forge, 1000.0)
    assert res_forge.success == False
    assert res_forge.failure_reason == "signature_invalid"

    # 009 Sequence violation (T-009)
    event_seq = seal.create_handoff_event("asset1", "A", "B", 1, 1010.0)
    res_seq = verifier.verify(event_seq, 1010.0)
    assert res_seq.success == False
    assert res_seq.failure_reason == "sequence_violation"
