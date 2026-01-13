import unittest
from unittest.mock import patch, MagicMock, Mock
import time
from decimal import Decimal
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.services.market_monitor import MarketMonitor
from poly_market_trader.models.portfolio import Portfolio
from poly_market_trader.models.trade import MarketDirection


class TestAutoBettingFeatures(unittest.TestCase):
    """Test cases for auto-betting features"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_place_informed_crypto_bet_bullish_confidence_high(self, mock_get_crypto_markets):
        """Test placing an informed crypto bet with high confidence bullish trend."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_123",
                "question": "Will Bitcoin reach $100k?",
                "description": "Bitcoin price prediction market"
            }
        ]
        
        # Mock the Chainlink analysis for bullish trend with high volatility
        with patch.object(self.trader, 'get_chainlink_analysis') as mock_get_analysis:
            mock_get_analysis.return_value = {
                'current_price': 50000.0,
                'trend': 'bullish',
                'indicators': {'volatility_15min': 3.0}  # High volatility for 15min timeframe
            }
            
            # Mock the order executor
            with patch.object(self.trader.order_executor, 'place_buy_order') as mock_place_order:
                mock_place_order.return_value = MagicMock()
                
                # Place an informed bet with high confidence threshold
                success = self.trader.place_informed_crypto_bet(
                    market_title_keyword="bitcoin",
                    amount=300.0,
                    max_price=0.7,
                    confidence_threshold=0.6,  # Moderate threshold
                    timeframe='15min'
                )
                
                # Verify the bet was placed
                self.assertTrue(success)
                mock_place_order.assert_called_once()
                
                # Verify the call was made with correct parameters
                args, kwargs = mock_place_order.call_args
                # The outcome parameter is the second positional argument (index 1)
                self.assertEqual(kwargs["outcome"], MarketDirection.YES)  # Bullish trend should lead to YES
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_place_informed_crypto_bet_bearish_confidence_high(self, mock_get_crypto_markets):
        """Test placing an informed crypto bet with high confidence bearish trend."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_456",
                "question": "Will Bitcoin crash?",
                "description": "Bitcoin price prediction market"
            }
        ]
        
        # Mock the Chainlink analysis for bearish trend with high volatility
        with patch.object(self.trader, 'get_chainlink_analysis') as mock_get_analysis:
            mock_get_analysis.return_value = {
                'current_price': 50000.0,
                'trend': 'bearish',
                'indicators': {'volatility_15min': 3.0}  # High volatility for 15min timeframe
            }
            
            # Mock the order executor
            with patch.object(self.trader.order_executor, 'place_buy_order') as mock_place_order:
                mock_place_order.return_value = MagicMock()
                
                # Place an informed bet with high confidence threshold
                success = self.trader.place_informed_crypto_bet(
                    market_title_keyword="bitcoin",
                    amount=300.0,
                    max_price=0.7,
                    confidence_threshold=0.6,  # Moderate threshold
                    timeframe='15min'
                )
                
                # Verify the bet was placed
                self.assertTrue(success)
                mock_place_order.assert_called_once()
                
                # Verify the call was made with correct parameters
                args, kwargs = mock_place_order.call_args
                # The outcome parameter is the second positional argument (index 1)
                self.assertEqual(kwargs["outcome"], MarketDirection.NO)  # Bearish trend should lead to NO
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_place_informed_crypto_bet_low_confidence_skip(self, mock_get_crypto_markets):
        """Test that low confidence bets are skipped."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_789",
                "question": "Will Bitcoin stay stable?",
                "description": "Bitcoin stability prediction market"
            }
        ]
        
        # Mock the Chainlink analysis for neutral trend with low volatility
        with patch.object(self.trader, 'get_chainlink_analysis') as mock_get_analysis:
            mock_get_analysis.return_value = {
                'current_price': 50000.0,
                'trend': 'neutral',
                'indicators': {'volatility_15min': 0.5}  # Low volatility
            }
            
            # Place an informed bet with high confidence threshold
            success = self.trader.place_informed_crypto_bet(
                market_title_keyword="bitcoin",
                amount=300.0,
                max_price=0.7,
                confidence_threshold=0.8,  # High threshold
                timeframe='15min'
            )
            
            # Verify the bet was NOT placed due to low confidence
            self.assertFalse(success)


class TestMarketMonitoring(unittest.TestCase):
    """Test cases for market monitoring features"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.portfolio = Portfolio(initial_balance=Decimal('10000.00'))
        self.market_data = Mock()
        self.chainlink_data = Mock()
        self.order_executor = Mock()
        self.monitor = MarketMonitor(
            portfolio=self.portfolio,
            market_data=self.market_data,
            chainlink_data=self.chainlink_data,
            order_executor=self.order_executor
        )
    
    def test_initial_monitoring_state(self):
        """Test initial state of the market monitor."""
        self.assertFalse(self.monitor.is_monitoring)
        self.assertEqual(self.monitor.check_interval, 900)  # Default 15 minutes
        self.assertEqual(len(self.monitor.active_bets), 0)
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        # Initially not monitoring
        self.assertFalse(self.monitor.is_monitoring)
        
        # Start monitoring
        self.monitor.start_monitoring(300)  # 5 minutes
        self.assertTrue(self.monitor.is_monitoring)
        self.assertEqual(self.monitor.check_interval, 300)
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor.is_monitoring)
    
    def test_monitoring_status(self):
        """Test getting monitoring status."""
        status = self.monitor.get_monitoring_status()
        self.assertFalse(status['is_monitoring'])
        self.assertEqual(status['active_bets_count'], 0)
        self.assertEqual(status['check_interval'], 900)
        
        # Change state and check again
        self.monitor.is_monitoring = True
        self.monitor.check_interval = 600
        
        status = self.monitor.get_monitoring_status()
        self.assertTrue(status['is_monitoring'])
        self.assertEqual(status['check_interval'], 600)
    
    def test_get_active_bets(self):
        """Test getting active bets."""
        # Initially no active bets
        active_bets = self.monitor.get_active_bets()
        self.assertEqual(len(active_bets), 0)
        
        # Add a mock bet
        mock_bet = {
            'trade': MagicMock(),
            'market_id': 'test_market',
            'outcome': MarketDirection.YES,
            'confidence': 0.8,
            'entry_price': 0.6,
            'quantity': 100.0,
            'timestamp': time.time()
        }
        self.monitor.active_bets.append(mock_bet)
        
        # Get active bets
        active_bets = self.monitor.get_active_bets()
        self.assertEqual(len(active_bets), 1)
        self.assertEqual(active_bets[0]['market_id'], 'test_market')
    
    @patch.object(MarketMonitor, '_extract_crypto_name')
    def test_analyze_and_bet_bullish_trend(self, mock_extract_crypto_name):
        """Test the _analyze_and_bet method with bullish trend."""
        # Mock the crypto name extraction
        mock_extract_crypto_name.return_value = 'bitcoin'
        
        # Mock market data
        market = {
            "id": "test_market_123",
            "question": "Will Bitcoin reach $100k?",
            "description": "Bitcoin price prediction market"
        }
        
        # Mock the chainlink data methods
        with patch.object(self.monitor.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 50000.0
            
            with patch.object(self.monitor.chainlink_data, 'get_recent_trend_15min') as mock_get_trend:
                mock_get_trend.return_value = 'bullish'
                
                with patch.object(self.monitor.chainlink_data, 'get_volatility_15min') as mock_get_volatility:
                    mock_get_volatility.return_value = 2.5  # High volatility
                    
                    with patch.object(self.monitor.market_data, 'get_market_prices') as mock_get_market_prices:
                        mock_get_market_prices.return_value = {"yes": {"price": 0.6}, "no": {"price": 0.4}}
                        
                        # Mock the order executor
                        with patch.object(self.monitor.order_executor, 'place_buy_order') as mock_place_order:
                            mock_place_order.return_value = MagicMock()
                            
                            # Call the method
                            self.monitor._analyze_and_bet(market)
                            
                            # Verify a bet was placed
                            mock_place_order.assert_called_once()
                            # Verify it was a YES bet (bullish trend)
                            args, kwargs = mock_place_order.call_args
                            # The outcome parameter is the second positional argument (index 1)
                            self.assertEqual(kwargs["outcome"], MarketDirection.YES)
    
    @patch.object(MarketMonitor, '_extract_crypto_name')
    def test_analyze_and_bet_bearish_trend(self, mock_extract_crypto_name):
        """Test the _analyze_and_bet method with bearish trend."""
        # Mock the crypto name extraction
        mock_extract_crypto_name.return_value = 'ethereum'
        
        # Mock market data
        market = {
            "id": "test_market_456",
            "question": "Will Ethereum crash?",
            "description": "Ethereum price prediction market"
        }
        
        # Mock the chainlink data methods
        with patch.object(self.monitor.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 4000.0
            
            with patch.object(self.monitor.chainlink_data, 'get_recent_trend_15min') as mock_get_trend:
                mock_get_trend.return_value = 'bearish'
                
                with patch.object(self.monitor.chainlink_data, 'get_volatility_15min') as mock_get_volatility:
                    mock_get_volatility.return_value = 2.5  # High volatility
                    
                    with patch.object(self.monitor.market_data, 'get_market_prices') as mock_get_market_prices:
                        mock_get_market_prices.return_value = {"yes": {"price": 0.4}, "no": {"price": 0.6}}
                        
                        # Mock the order executor
                        with patch.object(self.monitor.order_executor, 'place_buy_order') as mock_place_order:
                            mock_place_order.return_value = MagicMock()
                            
                            # Call the method
                            self.monitor._analyze_and_bet(market)
                            
                            # Verify a bet was placed
                            mock_place_order.assert_called_once()
                            # Verify it was a NO bet (bearish trend)
                            args, kwargs = mock_place_order.call_args
                            # The outcome parameter is the second positional argument (index 1)
                            self.assertEqual(kwargs["outcome"], MarketDirection.NO)
    
    @patch.object(MarketMonitor, '_extract_crypto_name')
    def test_analyze_and_bet_neutral_trend_skip(self, mock_extract_crypto_name):
        """Test the _analyze_and_bet method with neutral trend (should skip)."""
        # Mock the crypto name extraction
        mock_extract_crypto_name.return_value = 'bitcoin'
        
        # Mock market data
        market = {
            "id": "test_market_789",
            "question": "Will Bitcoin stay stable?",
            "description": "Bitcoin stability prediction market"
        }
        
        # Mock the chainlink data methods
        with patch.object(self.monitor.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 50000.0
            
            with patch.object(self.monitor.chainlink_data, 'get_recent_trend_15min') as mock_get_trend:
                mock_get_trend.return_value = 'neutral'
                
                with patch.object(self.monitor.chainlink_data, 'get_volatility_15min') as mock_get_volatility:
                    mock_get_volatility.return_value = 0.5  # Low volatility
                    
                    # Call the method
                    self.monitor._analyze_and_bet(market)
                    
                    # Verify no bet was placed due to neutral trend and low confidence
                    self.order_executor.place_buy_order.assert_not_called()


class TestPaperTraderMonitoringIntegration(unittest.TestCase):
    """Test cases for integration between PaperTrader and MarketMonitor"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
    
    def test_paper_trader_monitoring_methods(self):
        """Test that PaperTrader properly exposes monitoring methods."""
        # Verify the PaperTrader has the expected monitoring methods
        self.assertTrue(hasattr(self.trader, 'start_auto_betting'))
        self.assertTrue(hasattr(self.trader, 'stop_auto_betting'))
        self.assertTrue(hasattr(self.trader, 'get_auto_betting_status'))
        self.assertTrue(hasattr(self.trader, 'get_active_bets'))
    
    def test_start_auto_betting(self):
        """Test starting auto betting through PaperTrader."""
        # Initially not monitoring
        status = self.trader.get_auto_betting_status()
        self.assertFalse(status['is_monitoring'])
        
        # Start monitoring
        self.trader.start_auto_betting(180)  # 3 minutes
        status = self.trader.get_auto_betting_status()
        self.assertTrue(status['is_monitoring'])
        self.assertEqual(status['check_interval'], 180)
        
        # Stop monitoring
        self.trader.stop_auto_betting()
        status = self.trader.get_auto_betting_status()
        self.assertFalse(status['is_monitoring'])
    
    def test_get_active_bets_empty(self):
        """Test getting active bets when there are none."""
        active_bets = self.trader.get_active_bets()
        self.assertEqual(len(active_bets), 0)


if __name__ == '__main__':
    unittest.main()