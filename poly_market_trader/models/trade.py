from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TradeType(Enum):
    BUY = "buy"
    SELL = "sell"


class MarketDirection(Enum):
    YES = "YES"
    NO = "NO"


@dataclass
class Trade:
    """Represents a single trade in the market"""
    market_id: str
    outcome: MarketDirection
    quantity: float
    price: float
    trade_type: TradeType
    timestamp: datetime = None
    fee: float = 0.0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def total_value(self) -> float:
        """Calculate the total value of the trade"""
        return self.quantity * self.price


@dataclass
class Position:
    """Represents a position in a specific market"""
    market_id: str
    outcome: MarketDirection
    quantity: float
    avg_price: float
    entry_time: datetime = None
    
    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
    
    @property
    def current_value(self) -> float:
        """Current value of the position based on market price"""
        # This will be updated when market prices change
        return self.quantity * self.avg_price
    
    @property
    def pnl(self) -> float:
        """Profit and loss of the position"""
        # Placeholder - will be calculated based on current market price vs avg_price
        return 0.0