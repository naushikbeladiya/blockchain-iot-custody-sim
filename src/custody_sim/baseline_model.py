"""
Centralized-baseline tamper-detection model (R2).

Reviewer 1 (pp. 21-22) asked where the baseline tamper-detection rate comes
from. R1 stated 12.4% with no reproducible derivation. This module makes the
baseline an explicit, reproducible computation over the SAME injected attack
stream used for the blockchain system.

Threat model (matches manuscript Section 6.2.1):
An admin-credentialed insider (A2) can modify custody rows and rewrite the
audit log without application-visible evidence. The only tampering such an
insider cannot silently conceal is an event violating a database-level
referential-integrity constraint enforced at commit: a signature forgery
carrying a device key absent from the registry (foreign-key violation). All
other tampering is a well-formed row for a leg the insider controls and is
invisible at the database layer.

Detection rule: an adversarial event is detected IFF it is a signature forgery
with an unregistered key. Every forged signature here uses a key not in the
DeviceRegistry, so signature-forgery events are the detected set. No free
parameter is introduced.
"""
from __future__ import annotations
from dataclasses import dataclass

DETECTED_ATTACK_TYPES = {"signature_forgery"}

@dataclass
class BaselineResult:
    injected: int
    detected: int
    @property
    def tdr(self) -> float:
        return 0.0 if self.injected == 0 else self.detected / self.injected

def evaluate_baseline(events) -> BaselineResult:
    injected = detected = 0
    for e in events:
        if not getattr(e, "is_adversarial", False):
            continue
        injected += 1
        if getattr(e, "attack_type", None) in DETECTED_ATTACK_TYPES:
            detected += 1
    return BaselineResult(injected=injected, detected=detected)

__all__ = ["evaluate_baseline", "BaselineResult", "DETECTED_ATTACK_TYPES"]
