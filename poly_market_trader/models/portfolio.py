from dataclasses import dataclass
from typing import Dict, List
from .trade import Position, Trade
from decimal import Decimal


@dataclass
class Portfolio:
    """Manages the trader's portfolio with virtual funds"""
    initial_balance: Decimal = Decimal('10000.00')  # Starting with $10,000 virtual
    current_balance: Decimal = None
    positions: List[Position] = None
    trade_history: List[Trade] = None
    
    def __post_init__(self):
        if self.current_balance is None:
            self.current_balance = self.initial_balance
        if self.positions is None:
            self.positions = []
        if self.trade_history is None:
            self.trade_history = []
    
    def add_position(self, position: Position):
        """Add a new position to the portfolio"""
        self.positions.append(position)
    
    def remove_position(self, market_id: str, outcome: str):
        """Remove a position from the portfolio"""
        self.positions = [pos for pos in self.positions 
                         if not (pos.market_id == market_id and pos.outcome.value == outcome)]
    
    def update_balance(self, amount: Decimal):
        """Update the portfolio balance"""
        self.current_balance += amount
    
    def get_position(self, market_id: str, outcome: str) -> Position:
        """Get a specific position by market_id and outcome"""
        for pos in self.positions:
            if pos.market_id == market_id and pos.outcome.value == outcome:
                return pos
        return None
    
    def get_total_value(self, market_prices: Dict[str, Dict]) -> Decimal:
        """Calculate total portfolio value including positions"""
        total = self.current_balance

        for position in self.positions:
            market_data = market_prices.get(position.market_id)
            current_price = position.avg_price  # Default to cost basis

            if market_data:
                # market_data can be in different formats depending on where it comes from
                # Format 1: {"yes": {"price": 0.6}, "no": {"price": 0.4}}
                # Format 2: {"yes": 0.6, "no": 0.4}
                outcome_key = position.outcome.value.lower()

                if outcome_key in market_data:
                    outcome_data = market_data[outcome_key]
                    if isinstance(outcome_data, dict) and 'price' in outcome_data:
                        # Format 1: {"yes": {"price": 0.6}}
                        current_price = float(outcome_data['price'])
                    elif isinstance(outcome_data, (int, float)):
                        # Format 2: {"yes": 0.6}
                        current_price = float(outcome_data)
            
            # Add position value to total
            total += Decimal(str(position.quantity * current_price))

        return total

    def get_pnl(self, market_prices: Dict[str, Dict]) -> Decimal:
        """Calculate total profit and loss (Realized + Unrealized)"""
        # P&L = Current Total Value - Initial Balance
        total_value = self.get_total_value(market_prices)
        return total_value - self.initial_balance