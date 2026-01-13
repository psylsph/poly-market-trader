from typing import Dict, Optional
from ..models.trade import Trade, TradeType, MarketDirection
from ..models.portfolio import Portfolio
import uuid
from decimal import Decimal


class OrderExecutor:
    """Simulates order execution without real money"""
    
    def __init__(self, portfolio: Portfolio, storage=None):
        self.portfolio = portfolio
        self.storage = storage
    
    def execute_trade(self, market_id: str, outcome: MarketDirection, 
                     quantity: float, price: float, trade_type: TradeType) -> Optional[Trade]:
        """
        Execute a simulated trade
        :param market_id: The market ID to trade in
        :param outcome: The outcome to bet on (YES/NO)
        :param quantity: Quantity of shares to buy/sell
        :param price: Price at which to execute the trade
        :param trade_type: Type of trade (BUY/SELL)
        :return: Trade object if successful, None otherwise
        """
        total_cost = quantity * price
        
        # Check if we have enough balance for a buy order
        if trade_type == TradeType.BUY:
            if self.portfolio.current_balance < Decimal(str(total_cost)):
                print(f"Insufficient balance to buy {quantity} shares at ${price:.2f}. "
                      f"Required: ${total_cost:.2f}, Available: ${float(self.portfolio.current_balance):.2f}")
                return None
            
            # Deduct cost from balance
            self.portfolio.update_balance(Decimal(str(-total_cost)))
        
        # For sell orders, check if we have the position
        elif trade_type == TradeType.SELL:
            existing_position = self.portfolio.get_position(market_id, outcome.value)
            if not existing_position or existing_position.quantity < quantity:
                print(f"Cannot sell {quantity} shares. "
                      f"Position: {existing_position.quantity if existing_position else 0} shares available")
                return None
            
            # Add proceeds to balance
            self.portfolio.update_balance(Decimal(str(total_cost)))
            
            # Reduce position quantity
            existing_position.quantity -= quantity
            if existing_position.quantity <= 0:
                self.portfolio.remove_position(market_id, outcome.value)
        
        # Create the trade object
        trade = Trade(
            market_id=market_id,
            outcome=outcome,
            quantity=quantity,
            price=price,
            trade_type=trade_type
        )
        
        # Add to trade history
        self.portfolio.trade_history.append(trade)
        
        # Update or create position for buy orders
        if trade_type == TradeType.BUY:
            existing_position = self.portfolio.get_position(market_id, outcome.value)
            if existing_position:
                # Average the price if we already have a position
                total_qty = existing_position.quantity + quantity
                avg_price = ((existing_position.avg_price * existing_position.quantity) + (price * quantity)) / total_qty
                existing_position.quantity = total_qty
                existing_position.avg_price = avg_price
            else:
                # Create new position
                from ..models.trade import Position
                new_position = Position(
                    market_id=market_id,
                    outcome=outcome,
                    quantity=quantity,
                    avg_price=price
                )
                self.portfolio.add_position(new_position)
        
        print(f"Executed {trade_type.value.upper()} order: {quantity} shares of {outcome.value} "
              f"in market {market_id[:8]}... at ${price:.2f} each. Total: ${total_cost:.2f}")
        
        # Auto-save portfolio after trade execution
        if self.storage:
            self.storage.save_portfolio(self.portfolio)
        
        return trade
    
    def place_buy_order(self, market_id: str, outcome: MarketDirection, 
                       quantity: float, max_price: float) -> Optional[Trade]:
        """
        Place a simulated buy order
        :param market_id: The market ID to trade in
        :param outcome: The outcome to bet on (YES/NO)
        :param quantity: Quantity of shares to buy
        :param max_price: Maximum price willing to pay
        :return: Trade object if successful, None otherwise
        """
        # In a real implementation, we would check the order book
        # For simulation, we'll just use the current market price
        # For now, we'll assume the price is acceptable
        return self.execute_trade(market_id, outcome, quantity, max_price, TradeType.BUY)
    
    def place_sell_order(self, market_id: str, outcome: MarketDirection, 
                        quantity: float, min_price: float) -> Optional[Trade]:
        """
        Place a simulated sell order
        :param market_id: The market ID to trade in
        :param outcome: The outcome to sell (YES/NO)
        :param quantity: Quantity of shares to sell
        :param min_price: Minimum price willing to accept
        :return: Trade object if successful, None otherwise
        """
        # In a real implementation, we would check the order book
        # For simulation, we'll just use the current market price
        # For now, we'll assume the price is acceptable
        return self.execute_trade(market_id, outcome, quantity, min_price, TradeType.SELL)
    
    def get_available_balance(self) -> Decimal:
        """Get the available balance in the portfolio"""
        return self.portfolio.current_balance