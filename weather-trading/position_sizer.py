"""
Position Sizing for Weather Trading
Uses Half-Kelly criterion based on backtested win rates.
$1,000 bankroll configuration.
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class PositionSize:
    recommended_size: float
    kelly_fraction: float
    half_kelly_fraction: float
    max_size: float
    tier: str
    win_rate: float
    reason: str

# Backtested performance (726 trades, 5¢ min price filter)
TIER_STATS = {
    "HIGH": {
        "min_edge": 0.40,
        "win_rate": 0.82,
        "avg_return": 4.40,
        "max_bankroll_pct": 0.10,  # Max 10% per trade = $100
    },
    "MEDIUM": {
        "min_edge": 0.25,
        "win_rate": 0.51,
        "avg_return": 2.50,
        "max_bankroll_pct": 0.03,  # Max 3% per trade = $30
    },
    "LOW": {
        "min_edge": 0.15,
        "win_rate": 0.16,
        "avg_return": 1.50,
        "max_bankroll_pct": 0.01,  # Max 1% per trade = $10 (user override)
    },
}

class PositionSizer:
    def __init__(self, bankroll: float = 1000.0):
        self.bankroll = bankroll
        self.open_positions = 0.0
    
    def get_tier(self, edge: float) -> str:
        if edge >= TIER_STATS["HIGH"]["min_edge"]:
            return "HIGH"
        elif edge >= TIER_STATS["MEDIUM"]["min_edge"]:
            return "MEDIUM"
        return "LOW"
    
    def kelly_criterion(self, win_rate: float, avg_return: float) -> float:
        if avg_return <= 0:
            return 0.0
        p, q, b = win_rate, 1 - win_rate, avg_return
        return max(0.0, (p * b - q) / b)
    
    def calculate(self, edge: float, entry_price: float, liquidity: float = 500.0) -> PositionSize:
        tier = self.get_tier(edge)
        stats = TIER_STATS[tier]
        
        # LOW tier still calculates a size - user decides whether to trade
        
        kelly = self.kelly_criterion(stats["win_rate"], stats["avg_return"])
        half_kelly = kelly / 2
        
        available = self.bankroll - self.open_positions
        max_from_bankroll = available * stats["max_bankroll_pct"]
        max_from_liquidity = liquidity * 0.5
        kelly_size = available * half_kelly
        
        # LOW tier: use flat allocation since Kelly is negative EV
        if tier == "LOW":
            recommended = min(max_from_bankroll, max_from_liquidity)
        else:
            recommended = min(kelly_size, max_from_bankroll, max_from_liquidity)
        recommended = round(max(0, recommended), 2)
        
        return PositionSize(
            recommended_size=recommended,
            kelly_fraction=kelly,
            half_kelly_fraction=half_kelly,
            max_size=max_from_bankroll,
            tier=tier,
            win_rate=stats["win_rate"],
            reason=f"Half-Kelly capped at {stats['max_bankroll_pct']:.0%} bankroll"
        )
    
    def reserve(self, amount: float):
        self.open_positions += amount
    
    def release(self, amount: float):
        self.open_positions = max(0, self.open_positions - amount)
    
    def available_capital(self) -> float:
        return self.bankroll - self.open_positions

if __name__ == "__main__":
    sizer = PositionSizer(bankroll=1000.0)
    
    print("Position Sizing ($1,000 bankroll)")
    print("=" * 50)
    
    for edge, price in [(0.45, 0.35), (0.30, 0.50), (0.18, 0.70)]:
        pos = sizer.calculate(edge=edge, entry_price=price)
        icon = "🟢" if pos.tier == "HIGH" else "🟡" if pos.tier == "MEDIUM" else "🔴"
        print(f"\n{icon} Edge {edge:.0%}, Price {price:.0%}:")
        print(f"   Tier: {pos.tier} ({pos.win_rate:.0%} win rate)")
        print(f"   Size: ${pos.recommended_size:.2f}")
        print(f"   Kelly: {pos.kelly_fraction:.1%} → Half: {pos.half_kelly_fraction:.1%}")
