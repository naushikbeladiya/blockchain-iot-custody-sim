import simpy
import uuid
import os

from .topology import NetworkTopology
from .crypto_engine import generate_keypair
from .iot_seal import IoTSeal
from .contract_verifier import DeviceRegistry, AssetLedger, CustodyVerifier
from .adversary import AdversarialEngine
from .metrics import MetricsCollector
from .models import BlockchainBlock


class SystemSimulation:
    def __init__(self, config: dict):
        self.config = config
        self.env = simpy.Environment()
        self.topology = NetworkTopology(config)
        self.registry = DeviceRegistry()
        self.ledger = AssetLedger()
        self.verifier = CustodyVerifier(self.registry, self.ledger, config)
        self.adversary = AdversarialEngine(config)
        self.metrics = MetricsCollector(config)

        self.seals = {}          # asset_id -> IoTSeal
        self.private_keys = {}   # asset_id -> private_key
        # Pool of recently confirmed events eligible for replay attacks
        self._recent_confirmed = []

        self.total_handoffs = config.get("total_handoffs", 50000)
        self.handoffs_done = 0

        # Block times for latency calculation
        self.block_time_eth = config.get("block_time_ethereum", 12.0)
        self.block_time_l2  = config.get("block_time_layer2", 2.0)
        self.block_time_fast = config.get("block_time_fast", 0.4)
        self.skew_window = config.get("skew_window", 300)

    # ------------------------------------------------------------------
    # Simulation entry point
    # ------------------------------------------------------------------

    def run(self):
        done_event = self.env.event()
        self.env.process(self.parcel_generator(done_event))
        self.env.run(until=done_event)

    # ------------------------------------------------------------------
    # Parcel generation
    # ------------------------------------------------------------------

    def parcel_generator(self, done_event):
        """Generates parcels at Poisson arrival rate until total_handoffs reached."""
        rate = self.config.get("arrival_rate", 100) / 3600.0  # parcels/second

        while self.handoffs_done < self.total_handoffs:
            yield self.env.timeout(self.topology.rng.exponential(1.0 / rate))

            asset_id = str(uuid.uuid4())
            device_id = f"DEV_{asset_id[:8]}"
            priv, pub = generate_keypair()
            self.registry.register_device(device_id, pub)

            session_key = os.urandom(32)
            seal = IoTSeal(device_id, priv, pub, session_key)
            self.seals[asset_id] = seal
            self.private_keys[asset_id] = priv

            route = self.topology.generate_route()
            self.env.process(self.parcel_lifecycle(asset_id, seal, priv, route))

        done_event.succeed()

    # ------------------------------------------------------------------
    # Parcel lifecycle — one handoff per route segment
    # ------------------------------------------------------------------

    def parcel_lifecycle(self, asset_id: str, seal: IoTSeal, priv_key, route: list):
        for i in range(len(route) - 1):
            if self.handoffs_done >= self.total_handoffs:
                break

            sender   = route[i]
            receiver = route[i + 1]
            seq      = i + 1

            # Create a legitimate event at device time = env.now
            t_device = self.env.now
            legit_event = seal.create_handoff_event(asset_id, sender, receiver, seq, t_device)

            # The FIRST handoff in any parcel's lifecycle must be legitimate
            # so the ledger has a non-zero sequence baseline before attacks are attempted.
            is_first_handoff = (i == 0)
            is_adv = (not is_first_handoff) and (
                self.adversary.rng.random() < self.adversary.injection_rate
            )

            if is_adv:
                attack_type = self.adversary.rng.choice(
                    self.adversary.attack_names,
                    p=self.adversary.attack_probs
                )

                if attack_type == "replay_attack":
                    # Replay the current in-flight handoff (race-window model handled in _process_event)
                    event = self.adversary.replay_event(legit_event)
                else:
                    event = self.adversary.generate_attack(legit_event, priv_key, attack_type)
            else:
                event = legit_event

            # Simulate pre-block network latency (device → mempool)
            comm_latency = self.topology.get_communication_latency()
            cellular_latency = self.topology.get_cellular_latency()
            yield self.env.timeout(comm_latency + cellular_latency)

            # Process the event against all three blockchain configs
            self._process_event(event, t_device)
            self.handoffs_done += 1

            # Keep confirmed legit events in replay pool
            if not event.is_adversarial:
                self._recent_confirmed.append(legit_event)
                if len(self._recent_confirmed) > 200:
                    self._recent_confirmed.pop(0)

            # Inter-handoff wait (1–2 hours simulated time)
            yield self.env.timeout(self.topology.rng.uniform(3600, 7200))

    # ------------------------------------------------------------------
    # Block processing & metrics recording
    # ------------------------------------------------------------------

    def _process_event(self, event, t_device_created=None):
        """Verify event and record metrics for all three blockchain configs."""
        t_mempool = self.env.now  # arrival at mempool
        mempool_q = self.topology.get_mempool_queue_delay()

        # Confirmation time = mempool arrival + queueing + uniform wait for next block
        t_eth  = t_mempool + mempool_q + self.topology.rng.uniform(0, self.block_time_eth)
        t_l2   = t_mempool + mempool_q + self.topology.rng.uniform(0, self.block_time_l2)
        t_fast = t_mempool + mempool_q + self.topology.rng.uniform(0, self.block_time_fast)

        # For latency calculation: latency = confirm_time - device_create_time
        t_created = t_device_created if t_device_created is not None else event.timestamp

        # --- Replay attack edge-case model (race window) ---
        # Normal case: original confirms first ⇒ replay is rejected as duplicate.
        # Edge case: replay arrives before original confirmation ⇒ ~0.2% slip through.
        if event.is_adversarial and event.attack_type == "replay_attack":
            slip_rate = float(self.config.get("replay_slip_rate", 0.002))
            slips = (self.adversary.rng.random() < slip_rate)
            if not slips:
                # Emulate the "original already confirmed" state for duplicate detection.
                self.ledger.seen_hashes.add(event.composite_hash)

        # We run verification with the Ethereum confirmation timestamp as the canonical clock.
        verification_result = self.verifier.verify(event, t_eth)

        for config_name, t_confirm in [
            ("ethereum",       t_eth),
            ("layer2",         t_l2),
            ("high_throughput", t_fast),
        ]:
            block = BlockchainBlock(
                block_number=0,
                timestamp=t_confirm,
                base_fee_gwei={"ethereum": 30, "layer2": 5, "high_throughput": 1}[config_name],
                transactions=[event],
                gas_used=0,
                gas_limit=30_000_000,
                config_name=config_name,
            )
            self.metrics.record_event(event, verification_result, block, t_created)

    # ------------------------------------------------------------------
    # Convenience alias used by tests
    # ------------------------------------------------------------------

    def process_in_blockchains(self, event):
        self._process_event(event)
