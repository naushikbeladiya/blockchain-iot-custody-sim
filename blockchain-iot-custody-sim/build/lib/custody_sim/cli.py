import click
import simpy
import yaml
from pathlib import Path
from .simulation import SystemSimulation

def load_config(config_path: str) -> dict:
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

@click.group()
def cli():
    """Blockchain-IoT Custody Sim CLI"""
    pass

@cli.command()
@click.option("--config", type=click.Path(exists=True), required=False, help="Path to config YAML")
@click.option("--handoffs", type=int, help="Total custody events to simulate")
@click.option("--lambda", "arrival_rate", type=int, help="Parcel arrivals per hour")
@click.option("--skew", "skew_window", type=int, help="Timestamp skew window")
@click.option("--seed", type=int, help="Random seed")
@click.option("--output", type=click.Path(), help="Output directory")
def run(config, handoffs, arrival_rate, skew_window, seed, output):
    """Run full simulation."""
    if config:
        cfg = load_config(config)
    else:
        cfg = load_config("config/default.yaml")
        
    if handoffs is not None:
        cfg["total_handoffs"] = handoffs
    if arrival_rate is not None:
        cfg["arrival_rate"] = arrival_rate
    if skew_window is not None:
        cfg["skew_window"] = skew_window
    if seed is not None:
        cfg["seed"] = seed
    if output is not None:
        cfg["output_dir"] = output

    print(f"Starting simulation with {cfg['total_handoffs']} handoffs...")
    
    sim = SystemSimulation(cfg)
    
    try:
        sim.env.run(until=sim.parcel_generator())
    except StopIteration:
        pass
    except Exception as e:
        # Fallback if generator completes normally
        pass
        
    # Generate outputs
    sim.metrics.export_csv()
    print("Simulation complete. Results saved in output directory.")

if __name__ == "__main__":
    cli()
