"""
Re-run of the R1 latency analysis with the corrected inclusion model.

Everything upstream of block inclusion is UNCHANGED from R1 and is taken
directly from the published repository:

    custody_sim.topology.NetworkTopology.get_communication_latency()
    custody_sim.topology.NetworkTopology.get_cellular_latency()

Only the mempool/inclusion component is replaced (see inclusion_model.py).
This isolates the correction so the effect on Table 4 is attributable.

Protocol matches R1: 30 independent seeds (1-30), 95% CIs from the
t-distribution with 29 d.f.

Reproduces Table 4 of the IET Blockchain paper (BLC-2026-04-0069), including
the best-case reference row (p_incl = 1) and the share of events confirmed
within 15 s.

Usage (from the repository root):
    python3 run_latency.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from custody_sim.inclusion_model import REGIMES, build_profiles, OPTIMISTIC_CHALLENGE_WINDOW_S  # noqa: E402

N_SEEDS = 30
SEEDS = range(1, N_SEEDS + 1)
DF = N_SEEDS - 1
T_CRIT_95 = 2.045  # t(0.975, 29)

# Handoffs per seed. R1 used 50,000+; the latency pipeline is independent per
# event so this is a straight Monte Carlo over the same distribution.
N_EVENTS = 50_000


def _lognormal_params(mean: float, std: float) -> tuple[float, float]:
    """Exact parameterisation used in R1 topology.py."""
    var = std ** 2
    mu = np.log(mean ** 2 / np.sqrt(var + mean ** 2))
    sigma = np.sqrt(np.log(var / mean ** 2 + 1.0))
    return float(mu), float(sigma)


# Constants verified against custody_sim/topology.py:
#   get_communication_latency: lognormal, mean 200 ms, std 100 ms
#   get_cellular_latency:      lognormal, mean 1.6 s,  std 0.7 s
COMM_MU, COMM_SIGMA = _lognormal_params(200.0, 100.0)      # milliseconds
CELL_MU, CELL_SIGMA = _lognormal_params(1.6, 0.7)          # seconds


def verify_against_r1(repo: Path, n: int = 200_000) -> None:
    """
    Confirm the vectorised pre-block sampler reproduces R1's scalar functions.

    Guards against the vectorisation silently changing the distribution, which
    would contaminate the comparison between R1 and R2 numbers.
    """
    src = repo / "src"
    if not (src / "custody_sim" / "topology.py").exists():
        raise SystemExit(f"custody_sim not found under {src}")
    sys.path.insert(0, str(src))
    from custody_sim.topology import NetworkTopology  # type: ignore

    topo = NetworkTopology({"seed": 12345, "cellular_latency_mean_s": 1.6,
                            "cellular_latency_std_s": 0.7})
    rng_ref = np.random.default_rng(999)
    ref = np.array([topo.get_communication_latency(rng_ref)
                    + topo.get_cellular_latency(rng_ref) for _ in range(20_000)])

    rng_vec = np.random.default_rng(998)
    vec = sample_preblock(rng_vec, 20_000)

    print("pre-block sampler check (R1 scalar vs R2 vectorised):")
    print(f"  mean   R1 {ref.mean():.4f}s   R2 {vec.mean():.4f}s")
    print(f"  median R1 {np.median(ref):.4f}s   R2 {np.median(vec):.4f}s")
    print(f"  p95    R1 {np.percentile(ref,95):.4f}s   R2 {np.percentile(vec,95):.4f}s")
    if abs(ref.mean() - vec.mean()) > 0.05:
        raise SystemExit("pre-block sampler does not match R1 - aborting")
    print("  OK: distributions agree within Monte Carlo error\n")


def sample_preblock(rng, n: int) -> np.ndarray:
    """Device -> mempool arrival. Distribution identical to R1, vectorised."""
    comm_s = rng.lognormal(COMM_MU, COMM_SIGMA, size=n) / 1000.0
    cell_s = rng.lognormal(CELL_MU, CELL_SIGMA, size=n)
    return comm_s + cell_s


def sample_inclusion(prof, rng, n: int) -> np.ndarray:
    """Vectorised form of ChainProfile.sample_inclusion_delay."""
    residual = rng.uniform(0.0, prof.block_time, size=n)
    if prof.p_incl >= 1.0:
        return residual
    extra_blocks = rng.geometric(prof.p_incl, size=n) - 1
    return residual + extra_blocks * prof.block_time


def run_seed(seed: int, regime: str) -> dict:
    """One independent replication."""
    rng = np.random.default_rng(seed)
    pre = sample_preblock(rng, N_EVENTS)
    profiles = build_profiles(regime)

    out: dict[str, dict] = {}
    for key, prof in profiles.items():
        incl = sample_inclusion(prof, rng, N_EVENTS)
        total = pre + incl
        rec = {
            "median": float(np.median(total)),
            "mean": float(np.mean(total)),
            "p95": float(np.percentile(total, 95)),
            "p99": float(np.percentile(total, 99)),
            "frac_under_15s": float(np.mean(total < 15.0)),
            "mean_inclusion": float(np.mean(incl)),
            "mean_preblock": float(np.mean(pre)),
        }
        if prof.hard_finality_lag > 0:
            rec["median_hard"] = rec["median"] + prof.hard_finality_lag
        out[key] = rec
    return out


def ci95(values: list[float]) -> tuple[float, float, float]:
    """Mean and 95% CI half-width via t(29), matching R1's stated method."""
    a = np.asarray(values, dtype=float)
    m = float(a.mean())
    if a.std(ddof=1) == 0:
        return m, m, m
    hw = T_CRIT_95 * float(a.std(ddof=1)) / np.sqrt(len(a))
    return m, m - hw, m + hw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO_ROOT, type=Path)
    ap.add_argument("--out", default="results/latency_table4.json", type=Path)
    args = ap.parse_args()

    verify_against_r1(args.repo)

    results: dict[str, dict] = {}

    for regime in REGIMES:
        per_seed = [run_seed(s, regime) for s in SEEDS]
        chains = per_seed[0].keys()
        agg: dict[str, dict] = {}
        for chain in chains:
            agg[chain] = {}
            for metric in per_seed[0][chain]:
                vals = [ps[chain][metric] for ps in per_seed]
                m, lo, hi = ci95(vals)
                agg[chain][metric] = {"mean": m, "ci_low": lo, "ci_high": hi}
        results[regime] = agg

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2))

    # ---- report ----------------------------------------------------------
    profiles = build_profiles("normal")
    print("=" * 78)
    print("CORRECTED LATENCY MODEL - 30 seeds x 50,000 events, 95% CI via t(29)")
    print("=" * 78)

    for regime, p in REGIMES.items():
        print(f"\n### regime = {regime}   (p_incl = {p} on open-system chains)")
        eb = (1 - p) / p
        print(f"    expected extra blocks missed on Ethereum L1: {eb:.2f}")
        print(f"    {'chain':<34} {'median':>9} {'95% CI':>18} {'p95':>8} {'p99':>8} {'<15 s':>7}")
        for chain, rec in results[regime].items():
            med = rec["median"]
            print(
                f"    {profiles[chain].name:<34} "
                f"{med['mean']:>8.2f}s "
                f"[{med['ci_low']:>6.2f},{med['ci_high']:>6.2f}] "
                f"{rec['p95']['mean']:>7.2f}s {rec['p99']['mean']:>7.2f}s "
                f"{rec['frac_under_15s']['mean']*100:>6.1f}%"
            )
        eth = results[regime]["ethereum"]
        print(f"    Ethereum L1 fraction under 15 s: "
              f"{eth['frac_under_15s']['mean']*100:.1f}%")

    print("\n" + "-" * 78)
    print("L2 optimistic rollup, hard finality:")
    print(f"  soft (sequencer): {results['normal']['layer2_optimistic']['median']['mean']:.2f} s")
    print(f"  hard (L1 settlement + 7-day fraud-proof window): "
          f"{OPTIMISTIC_CHALLENGE_WINDOW_S/86400:.0f} days")
    print("-" * 78)

    print("\nConvergence check (R1 claimed L2 ~= high-throughput because")
    print("pre-block overhead dominates below ~2 s block times):")
    for regime in REGIMES:
        l2 = results[regime]["layer2_optimistic"]["median"]["mean"]
        fab = results[regime]["fabric"]["median"]["mean"]
        print(f"  {regime:<10} L2 {l2:6.2f}s   Fabric {fab:6.2f}s   gap {l2-fab:5.2f}s")
    pre = results["normal"]["ethereum"]["mean_preblock"]["mean"]
    print(f"\n  mean pre-block overhead (unchanged from R1): {pre:.2f}s")

    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
