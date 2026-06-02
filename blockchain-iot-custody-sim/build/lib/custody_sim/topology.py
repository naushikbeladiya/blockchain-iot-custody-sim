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
