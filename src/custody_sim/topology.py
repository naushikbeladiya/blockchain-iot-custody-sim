import numpy as np
from dataclasses import dataclass
import random
from typing import List, Tuple

@dataclass
class DistributionCenter:
    id: str
    location: str

@dataclass
class TransitHub:
    id: str
    location: str

@dataclass
class Courier:
    id: str
    location: str
    capacity: int

@dataclass
class Validator:
    id: str
    stake: float

class NetworkTopology:
    def __init__(self, config: dict):
        self.config = config
        self.distribution_centers = []
        self.transit_hubs = []
        self.couriers = []
        self.validators = []
        self._build_network()

    def _build_network(self):
        self.rng = np.random.default_rng(self.config.get('seed', 42))

        num_dc = self.config.get("num_distribution_centers", 5)
        for i in range(num_dc):
            self.distribution_centers.append(DistributionCenter(f"DC_{i}", f"Loc_DC_{i}"))

        num_th = self.config.get("num_transit_hubs", 12)
        for i in range(num_th):
            self.transit_hubs.append(TransitHub(f"TH_{i}", f"Loc_TH_{i}"))

        num_c = self.config.get("num_couriers", 48)
        for i in range(num_c):
            self.couriers.append(Courier(f"C_{i}", f"Loc_C_{i}", capacity=100))

        num_v = self.config.get("num_validators", 16)
        for i in range(num_v):
            self.validators.append(Validator(f"V_{i}", stake=self.rng.uniform(10, 100)))

    def generate_route(self, rng=None) -> List[str]:
        """
        Generates a route of 2-5 nodes.
        Starts at a DistributionCenter, passes through TransitHubs, ends with a Courier.
        Mean length 3.2 (truncated Poisson).
        """
        if rng is None:
            rng = self.rng

        mean = self.config.get("handoff_mean", 3.2)
        min_h = self.config.get("handoff_min", 2)
        max_h = self.config.get("handoff_max", 5)

        route_len = rng.poisson(mean)
        route_len = int(max(min_h, min(max_h, route_len)))

        route = []
        dc = rng.choice(self.distribution_centers)
        route.append(dc.id)

        if route_len > 2:
            num_th = route_len - 2
            available_th = [th.id for th in self.transit_hubs]
            chosen = rng.choice(available_th, size=num_th, replace=False)
            route.extend(chosen.tolist())

        c = rng.choice(self.couriers)
        route.append(c.id)

        return route

    def get_communication_latency(self, rng=None) -> float:
        """
        Returns a log-normal communication latency (ms → s).
        Mean 200 ms, std 100 ms.
        """
        if rng is None:
            rng = self.rng

        mean = 200.0
        std = 100.0
        var = std ** 2
        mu = np.log(mean ** 2 / np.sqrt(var + mean ** 2))
        sigma = np.sqrt(np.log(var / mean ** 2 + 1.0))

        latency_ms = rng.lognormal(mu, sigma)
        return latency_ms / 1000.0

    def get_cellular_latency(self, rng=None) -> float:
        """
        Cellular uplink latency in seconds (device → tower → backhaul).

        Default targets ~1–2.5s typical, with a light heavy-tail.
        Configurable via:
          - cellular_latency_mean_s (default 1.6)
          - cellular_latency_std_s  (default 0.7)
        """
        if rng is None:
            rng = self.rng

        mean = float(self.config.get("cellular_latency_mean_s", 1.6))
        std = float(self.config.get("cellular_latency_std_s", 0.7))
        # lognormal parameterization from desired mean/std
        var = std ** 2
        mu = np.log(mean ** 2 / np.sqrt(var + mean ** 2))
        sigma = np.sqrt(np.log(var / mean ** 2 + 1.0))
        return float(rng.lognormal(mu, sigma))

    def get_mempool_queue_delay(self, rng=None) -> float:
        """
        Mempool queuing / propagation delay before block inclusion (seconds).

        Default targets ~0.6–2.2s typical.
        Configurable via:
          - mempool_queue_min_s (default 0.6)
          - mempool_queue_max_s (default 2.2)
        """
        if rng is None:
            rng = self.rng
        qmin = float(self.config.get("mempool_queue_min_s", 0.6))
        qmax = float(self.config.get("mempool_queue_max_s", 2.2))
        if qmax < qmin:
            qmin, qmax = qmax, qmin
        return float(rng.uniform(qmin, qmax))
