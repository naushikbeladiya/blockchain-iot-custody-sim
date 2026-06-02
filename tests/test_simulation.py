import pytest
from custody_sim.simulation import SystemSimulation

def test_t010_t014_simulation_smoke_test():
    cfg = {
        "arrival_rate": 1000,  # fast arrivals
        "total_handoffs": 100,  # short run for CI
        "adversarial_rate": 0.10,
        "seed": 42,
        "num_distribution_centers": 5,
        "num_transit_hubs": 12,
        "num_couriers": 48,
        "skew_window": 300,
        "block_time_ethereum": 12.0,
        "block_time_layer2": 2.0,
        "block_time_fast": 0.4,
        "output_dir": "/tmp/test_results",
    }
    sim = SystemSimulation(cfg)
    sim.run()

    # Check that events were recorded
    assert len(sim.metrics.records) > 0
