import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from decimal import Decimal

from ..models.portfolio import Portfolio
from ..models.trade import Position, Trade, TradeType, MarketDirection


class PortfolioStorage:
    """Handles saving/loading portfolio data to/from JSON files"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.portfolio_file = self.data_dir / "portfolio.json"
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """Create data directory if it doesn't exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def save_portfolio(self, portfolio: Portfolio) -> None:
        """
        Save portfolio to JSON file
        :param portfolio: Portfolio object to save
        """
        data = {
            "version": "1.0",
            "initial_balance": float(portfolio.initial_balance),
            "current_balance": float(portfolio.current_balance),
            "positions": [],
            "trade_history": [],
            "stats": {
                "total_bets": len(portfolio.trade_history),
                "total_wins": 0,  # Will be tracked in Phase 2
                "total_losses": 0,  # Will be tracked in Phase 2
                "win_rate": 0.0,
                "realized_pnl": 0.0,
                "unrealized_pnl": 0.0,
                "total_pnl": 0.0,
                "roi": 0.0
            },
            "last_updated": datetime.now().isoformat()
        }
        
        # Serialize positions
        for position in portfolio.positions:
            data["positions"].append({
                "market_id": position.market_id,
                "outcome": position.outcome.value,
                "quantity": position.quantity,
                "avg_price": position.avg_price,
                "entry_time": position.entry_time.isoformat() if position.entry_time else None
            })
        
        # Serialize trade history
        for trade in portfolio.trade_history:
            data["trade_history"].append({
                "market_id": trade.market_id,
                "outcome": trade.outcome.value,
                "quantity": trade.quantity,
                "price": trade.price,
                "trade_type": trade.trade_type.value,
                "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
                "fee": trade.fee
            })
        
        # Write to file
        with open(self.portfolio_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Portfolio saved to {self.portfolio_file}")
    
    def load_portfolio(self) -> Optional[Portfolio]:
        """
        Load portfolio from JSON file
        :return: Portfolio object if file exists, None otherwise
        """
        if not self.portfolio_file.exists():
            return None
        
        try:
            with open(self.portfolio_file, 'r') as f:
                data = json.load(f)
            
            # Create Portfolio object
            portfolio = Portfolio(
                initial_balance=Decimal(str(data["initial_balance"])),
                current_balance=Decimal(str(data["current_balance"])),
                positions=[],
                trade_history=[]
            )
            
            # Deserialize positions
            for pos_data in data.get("positions", []):
                position = Position(
                    market_id=pos_data["market_id"],
                    outcome=MarketDirection(pos_data["outcome"]),
                    quantity=pos_data["quantity"],
                    avg_price=pos_data["avg_price"],
                    entry_time=datetime.fromisoformat(pos_data["entry_time"]) if pos_data.get("entry_time") else None
                )
                portfolio.positions.append(position)
            
            # Deserialize trade history
            for trade_data in data.get("trade_history", []):
                trade = Trade(
                    market_id=trade_data["market_id"],
                    outcome=MarketDirection(trade_data["outcome"]),
                    quantity=trade_data["quantity"],
                    price=trade_data["price"],
                    trade_type=TradeType(trade_data["trade_type"]),
                    timestamp=datetime.fromisoformat(trade_data["timestamp"]) if trade_data.get("timestamp") else None,
                    fee=trade_data.get("fee", 0.0)
                )
                portfolio.trade_history.append(trade)
            
            print(f"📂 Portfolio loaded from {self.portfolio_file}")
            print(f"   Balance: ${portfolio.current_balance:.2f} | Positions: {len(portfolio.positions)} | Trades: {len(portfolio.trade_history)}")
            
            return portfolio
        
        except Exception as e:
            print(f"❌ Error loading portfolio: {e}")
            return None
    
    def reset_portfolio(self, initial_balance: Decimal) -> Portfolio:
        """
        Reset portfolio to fresh state (wipe all data)
        :param initial_balance: Starting balance for new portfolio
        :return: Fresh Portfolio object
        """
        # Remove existing portfolio file
        if self.portfolio_file.exists():
            self.portfolio_file.unlink()
            print(f"🗑️  Removed existing portfolio file")
        
        # Create new portfolio
        portfolio = Portfolio(initial_balance=initial_balance)
        print(f"✨ Created new portfolio with ${initial_balance:.2f} balance")
        
        # Save immediately
        self.save_portfolio(portfolio)
        
        return portfolio
    
    def portfolio_exists(self) -> bool:
        """Check if portfolio file exists"""
        return self.portfolio_file.exists()
