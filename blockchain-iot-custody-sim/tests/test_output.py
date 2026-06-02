import pytest
from custody_sim.metrics import MetricsCollector

def test_t015_output_files(tmp_path):
    cfg = {"output_dir": str(tmp_path)}
    mc = MetricsCollector(cfg)
    # mock a record
    class MockResult:
        success = True
        failure_reason = None
        gas_used_naive = 200000
        gas_used_optimized = 150000
    class MockBlock:
        timestamp = 1010.0
        config_name = "ethereum"
    class MockEvent:
        event_id = "test"
        is_adversarial = False
        attack_type = None
        timestamp = 1000.0
        
    mc.record_event(MockEvent(), MockResult(), MockBlock())
    mc.export_csv()
    
    import os
    assert os.path.exists(os.path.join(str(tmp_path), "raw_data.csv"))
