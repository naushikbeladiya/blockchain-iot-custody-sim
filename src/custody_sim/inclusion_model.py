"""
Corrected block-inclusion latency model for BLC-2026-04-0069 (R2).

Addresses Reviewer 1, semantic comment 1:

    "in public blockchains, TXs are coming from everywhere not just your system
     and hence latency time should be calculated according to the average
     waiting time for the TX in the minting mempool"

ORIGINAL MODEL (custody_sim/simulation.py::_process_event, R1)
--------------------------------------------------------------
    mempool_q = rng.uniform(0.6, 2.2)          # same for ALL chains
    t_conf    = t_mempool + mempool_q + rng.uniform(0, block_time)

Three defects:

  D1. The mempool delay is a single fixed distribution applied identically to
      Ethereum L1, L2 and the high-throughput configuration. Contention is a
      property of the chain, not a constant.
  D2. `uniform(0, block_time)` implies inclusion in the VERY NEXT block with
      probability 1. On a public chain a transaction competes for finite block
      space against exogenous demand and may miss several blocks.
  D3. No coupling between fee bid and inclusion probability, so EIP-1559
      dynamics play no role despite being cited in the paper.

CORRECTED MODEL
---------------
Inclusion delay decomposes into two independent parts:

    delay = residual + (G - 1) * block_time,      G ~ Geometric(p_incl)

  * residual ~ U(0, block_time)
        Time from mempool arrival to the next block boundary. A transaction
        arrives at a uniformly random point in the block interval. This part
        of the original model was correct and is retained.

  * (G - 1) * block_time
        Additional whole blocks missed before inclusion. G is the number of
        block opportunities until the first success, so E[G] = 1/p_incl and
        E[extra blocks] = (1 - p_incl)/p_incl.

`p_incl` is the per-block probability that this transaction is included given
its fee bid relative to competing demand. It is the single parameter carrying
the open-system behaviour the reviewer asked for:

    p_incl = 1.0   closed system (permissioned): no exogenous transactions,
                   inclusion in the next block is guaranteed. This is exactly
                   the original model, which is therefore CORRECT for Fabric.
    p_incl < 1.0   open system (public L1 / L2): exogenous load competes for
                   block space.

Deployment semantics
--------------------
Ethereum L1  open system. p_incl set by congestion regime.
L2 optimistic rollup
             TWO distinct finality points, reported separately:
               soft — sequencer inclusion. Fast and near-deterministic, but a
                      trust assumption on a centralised sequencer, not a
                      cryptographic guarantee.
               hard — L1 settlement plus the fraud-proof challenge window
                      (7 days on Arbitrum One / OP Mainnet). This is when the
                      custody record becomes censorship-resistant evidence.
             The R1 manuscript reported only soft finality while claiming
             evidentiary strength. For a chain-of-custody system that
             conflation is material.
Fabric       closed system. p_incl = 1.0, deterministic finality at commit.

Congestion regimes
------------------
p_incl is reported across three regimes rather than fixed, so no single
congestion assumption carries the paper's conclusions.

Author: prepared for N. Beladiya, R2 revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Congestion regimes
# ---------------------------------------------------------------------------
# p_incl is the per-block inclusion probability for a transaction bidding at
# roughly the median of the pending priority-fee distribution.
#
#   normal     — base fee near the EIP-1559 target of 15M gas; a median-fee
#                transaction lands in the next block the large majority of the
#                time. E[extra blocks] = 0.11
#   moderate   — sustained demand above target; ~1 extra block on average.
#   congested  — demand well above target, base fee climbing; a median-fee
#                transaction waits several blocks.
#
# These are scenario definitions, NOT measurements. State them as such in the
# manuscript. If a reviewer asks for empirical grounding, replace p_incl with
# an inclusion-delay distribution fitted to mempool data over a stated window.

REGIMES: dict[str, float] = {
    # best_case — reference point only: every transaction is included in the
    #             first block after it arrives (exclusive access to block
    #             space). Reported as the "best case" row of Table 4.
    "best_case": 1.00,
    "normal":    0.90,
    "moderate":  0.50,
    "congested": 0.25,
}

# Fraud-proof challenge window for optimistic rollups (Arbitrum One, OP
# Mainnet). Seconds.
OPTIMISTIC_CHALLENGE_WINDOW_S: float = 7 * 24 * 3600.0


@dataclass
class ChainProfile:
    """Inclusion characteristics of one deployment target."""

    name: str
    block_time: float
    p_incl: float
    open_system: bool
    # Delay from soft (sequencer) to hard (L1-settled) finality. Zero for
    # chains where inclusion is finality.
    hard_finality_lag: float = 0.0
    notes: str = ""

    def sample_inclusion_delay(self, rng) -> float:
        """Mempool arrival -> block inclusion, in seconds."""
        residual = rng.uniform(0.0, self.block_time)
        if self.p_incl >= 1.0:
            return float(residual)
        # rng.geometric returns G >= 1 (trials until first success).
        extra_blocks = rng.geometric(self.p_incl) - 1
        return float(residual + extra_blocks * self.block_time)

    def expected_extra_blocks(self) -> float:
        if self.p_incl >= 1.0:
            return 0.0
        return (1.0 - self.p_incl) / self.p_incl


def build_profiles(regime: str) -> dict[str, ChainProfile]:
    """Chain profiles for a named congestion regime."""
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}; expected one of {sorted(REGIMES)}")
    p = REGIMES[regime]

    return {
        # --- Ethereum L1: open system, contention applies -------------------
        "ethereum": ChainProfile(
            name="Ethereum L1 (PoS)",
            block_time=12.0,
            p_incl=p,
            open_system=True,
            hard_finality_lag=0.0,
            notes="Inclusion delay under exogenous contention. Economic "
                  "finality (2 epochs, ~12.8 min) reported separately in text.",
        ),

        # --- L2 optimistic rollup: soft vs hard finality ---------------------
        # The sequencer is a single operator ordering its own queue, so
        # inclusion is near-deterministic (p high) regardless of L1 congestion.
        # The exposure is not queueing delay but the trust assumption plus the
        # challenge window before the record is settled evidence.
        "layer2_optimistic": ChainProfile(
            name="L2 optimistic rollup (sequencer)",
            block_time=2.0,
            p_incl=0.99,
            open_system=False,
            hard_finality_lag=OPTIMISTIC_CHALLENGE_WINDOW_S,
            notes="Soft finality at the sequencer; hard finality after L1 "
                  "settlement plus a 7-day fraud-proof window.",
        ),

        # --- Permissioned: closed system ------------------------------------
        # Only this system's transactions enter the queue, so the R1 model was
        # already correct here. p_incl = 1.0 reproduces it exactly.
        "fabric": ChainProfile(
            name="Hyperledger Fabric (permissioned)",
            block_time=0.4,
            p_incl=1.0,
            open_system=False,
            hard_finality_lag=0.0,
            notes="Closed system: no exogenous transactions. Deterministic "
                  "finality at commit.",
        ),
    }


__all__ = [
    "REGIMES",
    "OPTIMISTIC_CHALLENGE_WINDOW_S",
    "ChainProfile",
    "build_profiles",
]
