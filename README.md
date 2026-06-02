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

## Releasing / zipping for GitHub submission
If you need a single zip, make sure it includes the Python sources under `src/` (that’s where the simulator lives).

From the repo root:

```bash
cd blockchain-iot-custody-sim
zip -r custody-sim.zip src config tests pyproject.toml README.md LICENSE
```

## License
MIT License
