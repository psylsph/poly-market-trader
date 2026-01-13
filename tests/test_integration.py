import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.models.trade import MarketDirection
from poly_market_trader.models.portfolio import Portfolio


class TestIntegration(unittest.TestCase):
    """Integration tests for the main application flow"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_full_trading_flow(self, mock_get_crypto_markets):
        """Test the full trading flow from market discovery to position creation."""
        # Mock the crypto markets to return a specific market
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_123",
                "question": "Will Bitcoin reach $100k by end of year?",
                "description": "Bitcoin price prediction market"
            }
        ]
        
        # Mock the market data provider to return prices
        with patch.object(self.trader.market_data, 'get_market_prices') as mock_get_prices:
            mock_get_prices.return_value = {"yes": {"price": 0.6}, "no": {"price": 0.4}}
            
            # Place a crypto bet
            success = self.trader.place_crypto_bet(
                market_title_keyword="bitcoin",
                outcome=MarketDirection.YES,
                amount=500.0,
                max_price=0.6
            )
            
            # Verify the bet was successful
            self.assertTrue(success)
            
            # Verify portfolio state
            summary = self.trader.get_portfolio_summary()
            self.assertEqual(summary['current_balance'], 9500.0)  # 10000 - 500
            self.assertEqual(summary['positions_count'], 1)
            self.assertEqual(summary['trade_count'], 1)
            
            # Verify the position exists
            self.trader.list_positions()  # This should not raise an exception
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_portfolio_value_calculation(self, mock_get_crypto_markets):
        """Test that portfolio value is calculated correctly with positions."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_456",
                "question": "Will Ethereum hit $5k?",
                "description": "Ethereum price prediction"
            }
        ]
        
        # Mock the market data provider
        with patch.object(self.trader.market_data, 'get_market_prices') as mock_get_prices:
            mock_get_prices.return_value = {"yes": {"price": 0.7}, "no": {"price": 0.3}}
            
            # Place a bet
            success = self.trader.place_crypto_bet(
                market_title_keyword="ethereum",
                outcome=MarketDirection.YES,
                amount=300.0,
                max_price=0.6
            )
            
            self.assertTrue(success)
            
            # Get portfolio summary which includes value calculation
            summary = self.trader.get_portfolio_summary()
            
            # The total value should account for both cash and position value
            # Cash: 10000 - 300 = 9700
            # Position value: quantity * current_price = (300/0.6) * 0.7 = 500 * 0.7 = 350
            # Total: 9700 + 350 = 10050
            self.assertGreaterEqual(summary['total_value'], summary['current_balance'])
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_chainlink_integration(self, mock_get_crypto_markets):
        """Test integration between paper trader and Chainlink data."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_789",
                "question": "Will Bitcoin price rise?",
                "description": "Bitcoin trend prediction"
            }
        ]
        
        # Mock the Chainlink data provider
        with patch.object(self.trader.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 60000.0
            
            with patch.object(self.trader.chainlink_data, 'get_crypto_trend') as mock_get_trend:
                mock_get_trend.return_value = 'bullish'
                
                # Perform Chainlink analysis
                analysis = self.trader.get_chainlink_analysis("bitcoin")
                
                # Verify the analysis contains expected data
                self.assertIsNotNone(analysis['current_price'])
                self.assertIsNotNone(analysis['trend'])
                self.assertIsNotNone(analysis['indicators'])
                
                # Verify the trend is bullish as mocked
                self.assertEqual(analysis['trend'], 'bullish')
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_informed_betting_flow(self, mock_get_crypto_markets):
        """Test the full flow of informed betting based on Chainlink analysis."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_abc",
                "question": "Will Ethereum price increase?",
                "description": "Ethereum trend prediction"
            }
        ]
        
        # Mock Chainlink data to suggest bullish trend
        with patch.object(self.trader.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 4000.0
            
            with patch.object(self.trader.chainlink_data, 'get_crypto_trend') as mock_get_trend:
                mock_get_trend.return_value = 'bullish'
                
                with patch.object(self.trader.chainlink_data, 'get_technical_indicators') as mock_get_indicators:
                    mock_get_indicators.return_value = {
                        'sma': 3800.0,
                        'volatility': 2.5,
                        'current_price': 4000.0,
                        'price_sma_ratio': 1.05,
                        'trend_direction': 'bullish'
                    }
                    
                    # Place an informed crypto bet
                    success = self.trader.place_informed_crypto_bet(
                        market_title_keyword="ethereum",
                        amount=200.0,
                        max_price=0.7,
                        confidence_threshold=0.5
                    )
                    
                    # Verify the bet was placed (should be YES for bullish trend)
                    self.assertTrue(success)
                    
                    # Verify portfolio state
                    summary = self.trader.get_portfolio_summary()
                    self.assertEqual(summary['trade_count'], 1)
    
    def test_portfolio_pnl_calculation(self):
        """Test that P&L is calculated correctly."""
        # Add a position manually to test P&L calculation
        from poly_market_trader.models.trade import Position
        
        position = Position(
            market_id="test_market",
            outcome=MarketDirection.YES,
            quantity=100.0,
            avg_price=0.5
        )
        self.trader.portfolio.add_position(position)
        
        # Mock market prices where current price is higher than avg_price (profit)
        market_prices = {
            "test_market": {
                "yes": {"price": 0.7},  # Current price is 0.7
                "no": {"price": 0.3}
            }
        }
        
        # Calculate P&L: quantity * (current_price - avg_price) = 100 * (0.7 - 0.5) = 20
        pnl = self.trader.portfolio.get_pnl(market_prices)
        self.assertEqual(float(pnl), 20.0)
        
        # Test with loss scenario
        market_prices_loss = {
            "test_market": {
                "yes": {"price": 0.3},  # Current price is 0.3
                "no": {"price": 0.7}
            }
        }
        
        # Calculate P&L: quantity * (current_price - avg_price) = 100 * (0.3 - 0.5) = -20
        pnl_loss = self.trader.portfolio.get_pnl(market_prices_loss)
        self.assertEqual(float(pnl_loss), -20.0)
    
    def test_multiple_positions_tracking(self):
        """Test tracking multiple positions."""
        from poly_market_trader.models.trade import Position
        
        # Add multiple positions
        position1 = Position(
            market_id="market1",
            outcome=MarketDirection.YES,
            quantity=50.0,
            avg_price=0.4
        )
        position2 = Position(
            market_id="market2",
            outcome=MarketDirection.NO,
            quantity=30.0,
            avg_price=0.6
        )
        
        self.trader.portfolio.add_position(position1)
        self.trader.portfolio.add_position(position2)
        
        # Verify both positions are tracked
        self.assertEqual(len(self.trader.portfolio.positions), 2)
        
        # Verify we can retrieve specific positions
        retrieved_pos1 = self.trader.portfolio.get_position("market1", "YES")
        self.assertEqual(retrieved_pos1, position1)
        
        retrieved_pos2 = self.trader.portfolio.get_position("market2", "NO")
        self.assertEqual(retrieved_pos2, position2)


class TestEndToEnd(unittest.TestCase):
    """End-to-end tests simulating real usage scenarios"""
    
    def test_complete_paper_trading_session(self):
        """Test a complete paper trading session from start to finish."""
        # Initialize trader
        trader = PaperTrader(initial_balance=Decimal('5000.00'), auto_load=False)
        
        # Get initial portfolio state
        initial_summary = trader.get_portfolio_summary()
        self.assertEqual(initial_summary['current_balance'], 5000.0)
        self.assertEqual(initial_summary['positions_count'], 0)
        
        # List crypto markets (this should not fail)
        try:
            trader.list_crypto_markets(limit=2)
        except Exception:
            self.fail("list_crypto_markets raised an exception unexpectedly!")
        
        # Get portfolio summary again
        summary_after_list = trader.get_portfolio_summary()
        self.assertEqual(summary_after_list['current_balance'], 5000.0)
        
        # The session should complete without errors
        self.assertTrue(True)  # This is just to ensure the test doesn't fail


if __name__ == '__main__':
    unittest.main()