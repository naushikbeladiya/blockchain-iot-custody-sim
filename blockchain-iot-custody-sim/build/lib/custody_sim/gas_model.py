class EIP1559GasModel:
    def __init__(self, base_fee_initial: float, elasticity_multiplier: float = 2.0, target_utilization: float = 0.5):
        self.base_fee = base_fee_initial
        self.elasticity_multiplier = elasticity_multiplier
        self.target_utilization = target_utilization

    def compute_next_base_fee(self, block_utilization: float) -> float:
        """
        Updates and returns the base fee based on EIP-1559 formula.
        Capped at 12.5% change per block.
        """
        if block_utilization > self.target_utilization:
            delta = 0.125 * (block_utilization - self.target_utilization) / self.target_utilization
            # Maximum 12.5% increase
            delta = min(0.125, delta)
            self.base_fee = self.base_fee * (1 + delta)
        elif block_utilization < self.target_utilization:
            delta = 0.125 * (self.target_utilization - block_utilization) / self.target_utilization
            # Maximum 12.5% decrease
            delta = min(0.125, delta)
            self.base_fee = self.base_fee * (1 - delta)
            
        # Ensure base fee doesn't drop below some minimum sanity (e.g. 1 gwei)
        self.base_fee = max(1.0, self.base_fee)
        return self.base_fee

    def calculate_usd_cost(self, gas_used: int, priority_fee_gwei: float, eth_price_usd: float) -> float:
        cost_eth = (gas_used * (self.base_fee + priority_fee_gwei)) / 1e9
        return cost_eth * eth_price_usd
