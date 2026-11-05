# Blockchain-IoT Custody Chain Simulation

Discrete-event simulation framework for a three-tier blockchain-IoT cryptographic chain-of-custody system for last-mile parcel delivery.

## Installation
```bash
git clone https://github.com/naushikbeladiya/blockchain-iot-custody-sim.git
cd blockchain-iot-custody-sim
pip install -e .
```

## Usage
Run full paper reproduction simulation:
```bash
custody-sim run --config config/paper_reproduction.yaml --output ./results
```

Run quick test:
```bash
custody-sim run --handoffs 1000 --output ./results-quick
```

## Reproducing the published results (IET Blockchain, BLC-2026-04-0069)

From the repository root, with the package dependencies installed:

```bash
# Table 4 — confirmation latency under mempool contention, incl. best-case row and share within 15 s
python3 run_latency.py

# Section 6.2.2 — centralized-baseline tamper detection rate (admin-insider, A2)
python3 run_baseline.py
```

Both scripts run 30 seeds (1–30) and report 95% confidence intervals from the t-distribution with 29 d.f.
The block-inclusion model is in `src/custody_sim/inclusion_model.py`. Its contention regimes map to the paper as
`best_case` (p = 1.00, best case), `normal` (p = 0.90, benign), `moderate` (p = 0.50) and `congested` (p = 0.25).
These regimes are defined scenarios, not measurements. The baseline detector is in `src/custody_sim/baseline_model.py`.

## Releasing / zipping for GitHub submission
If you need a single zip, make sure it includes the Python sources under `src/` (that’s where the simulator lives).

From the repo root:

```bash
cd blockchain-iot-custody-sim
zip -r custody-sim.zip src config tests pyproject.toml README.md LICENSE
```

## License
MIT License
