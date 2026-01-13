import unittest
from decimal import Decimal
from datetime import datetime
from poly_market_trader.models.trade import Trade, Position, TradeType, MarketDirection
from poly_market_trader.models.portfolio import Portfolio


class TestTradeModel(unittest.TestCase):
    """Test cases for the Trade model"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trade = Trade(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            price=0.6,
            trade_type=TradeType.BUY
        )
    
    def test_trade_creation(self):
        """Test that a trade is created with correct attributes."""
        self.assertEqual(self.trade.market_id, "test_market")
        self.assertEqual(self.trade.outcome, MarketDirection.YES)
        self.assertEqual(self.trade.quantity, 10.0)
        self.assertEqual(self.trade.price, 0.6)
        self.assertEqual(self.trade.trade_type, TradeType.BUY)
        self.assertIsNotNone(self.trade.timestamp)
        self.assertEqual(type(self.trade.timestamp), datetime)
    
    def test_trade_total_value(self):
        """Test that total value is calculated correctly."""
        self.assertEqual(self.trade.total_value, 6.0)  # 10.0 * 0.6
    
    def test_trade_fee_default(self):
        """Test that fee defaults to 0.0."""
        self.assertEqual(self.trade.fee, 0.0)


class TestPositionModel(unittest.TestCase):
    """Test cases for the Position model"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.6
        )
    
    def test_position_creation(self):
        """Test that a position is created with correct attributes."""
        self.assertEqual(self.position.market_id, "test_market")
        self.assertEqual(self.position.outcome, MarketDirection.YES)
        self.assertEqual(self.position.quantity, 10.0)
        self.assertEqual(self.position.avg_price, 0.6)
        self.assertIsNotNone(self.position.entry_time)
        self.assertEqual(type(self.position.entry_time), datetime)
    
    def test_position_current_value(self):
        """Test that current value is calculated correctly."""
        # Note: current_value uses avg_price as a placeholder
        self.assertEqual(self.position.current_value, 6.0)  # 10.0 * 0.6
    
    def test_position_pnl(self):
        """Test that P&L is calculated correctly."""
        # Note: pnl uses avg_price as a placeholder
        self.assertEqual(self.position.pnl, 0.0)


class TestPortfolioModel(unittest.TestCase):
    """Test cases for the Portfolio model"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.portfolio = Portfolio(initial_balance=Decimal('1000.00'))
    
    def test_portfolio_initialization(self):
        """Test that portfolio is initialized with correct attributes."""
        self.assertEqual(self.portfolio.initial_balance, Decimal('1000.00'))
        self.assertEqual(self.portfolio.current_balance, Decimal('1000.00'))
        self.assertEqual(len(self.portfolio.positions), 0)
        self.assertEqual(len(self.portfolio.trade_history), 0)
    
    def test_portfolio_with_custom_initial_balance(self):
        """Test that portfolio can be initialized with custom balance."""
        portfolio = Portfolio(initial_balance=Decimal('500.00'))
        self.assertEqual(portfolio.initial_balance, Decimal('500.00'))
        self.assertEqual(portfolio.current_balance, Decimal('500.00'))
    
    def test_add_position(self):
        """Test adding a position to the portfolio."""
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.6
        )
        self.portfolio.add_position(position)
        
        self.assertEqual(len(self.portfolio.positions), 1)
        self.assertEqual(self.portfolio.positions[0], position)
    
    def test_remove_position(self):
        """Test removing a position from the portfolio."""
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.6
        )
        self.portfolio.add_position(position)
        
        self.portfolio.remove_position("test_market", "YES")
        self.assertEqual(len(self.portfolio.positions), 0)
    
    def test_get_position_found(self):
        """Test getting an existing position."""
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.6
        )
        self.portfolio.add_position(position)
        
        found_position = self.portfolio.get_position("test_market", "YES")
        self.assertEqual(found_position, position)
    
    def test_get_position_not_found(self):
        """Test getting a non-existing position."""
        position = self.portfolio.get_position("nonexistent", "YES")
        self.assertIsNone(position)
    
    def test_update_balance_positive(self):
        """Test updating balance with a positive amount."""
        initial_balance = self.portfolio.current_balance
        self.portfolio.update_balance(Decimal('100.00'))
        expected_balance = initial_balance + Decimal('100.00')
        self.assertEqual(self.portfolio.current_balance, expected_balance)
    
    def test_update_balance_negative(self):
        """Test updating balance with a negative amount."""
        initial_balance = self.portfolio.current_balance
        self.portfolio.update_balance(Decimal('-100.00'))
        expected_balance = initial_balance - Decimal('100.00')
        self.assertEqual(self.portfolio.current_balance, expected_balance)
    
    def test_get_total_value_no_positions(self):
        """Test getting total value when there are no positions."""
        market_prices = {}
        total_value = self.portfolio.get_total_value(market_prices)
        self.assertEqual(total_value, Decimal('1000.00'))
    
    def test_get_total_value_with_positions(self):
        """Test getting total value when there are positions."""
        # Add a position
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.6
        )
        self.portfolio.add_position(position)
        
        # Mock market prices
        market_prices = {
            "test_market": {
                "yes": {"price": 0.7},
                "no": {"price": 0.3}
            }
        }
        
        # Total value should be current balance + position value
        # Position value = quantity * current_price = 10.0 * 0.7 = 7.0
        total_value = self.portfolio.get_total_value(market_prices)
        expected_value = Decimal('1000.00') + Decimal('7.0')
        self.assertEqual(total_value, expected_value)
    
    def test_get_pnl_no_positions(self):
        """Test getting P&L when there are no positions."""
        market_prices = {}
        pnl = self.portfolio.get_pnl(market_prices)
        self.assertEqual(pnl, Decimal('0'))
    
    def test_get_pnl_with_positions(self):
        """Test getting P&L when there are positions."""
        # Add a position
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=10.0,
            avg_price=0.5  # Bought at 0.5
        )
        self.portfolio.add_position(position)
        
        # Mock market prices - current price is 0.7
        market_prices = {
            "test_market": {
                "yes": {"price": 0.7},  # Current price is 0.7
                "no": {"price": 0.3}
            }
        }
        
        # P&L = quantity * (current_price - avg_price) = 10.0 * (0.7 - 0.5) = 2.0
        pnl = self.portfolio.get_pnl(market_prices)
        self.assertEqual(pnl, Decimal('2.0'))


if __name__ == '__main__':
    unittest.main()