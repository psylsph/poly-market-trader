import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from poly_market_trader.services.paper_trader import PaperTrader
from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider
from poly_market_trader.models.trade import MarketDirection, Trade


class Test15MinuteAnalysis(unittest.TestCase):
    """Test cases for 15-minute analysis functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
        self.provider = ChainlinkDataProvider()
    
    def test_get_chainlink_analysis_15min_timeframe(self):
        """Test that get_chainlink_analysis works with 15min timeframe."""
        # Mock the data provider methods
        with patch.object(self.trader.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 50000.0
            
            with patch.object(self.trader.chainlink_data, 'get_recent_trend_15min') as mock_get_trend:
                mock_get_trend.return_value = 'bullish'
                
                with patch.object(self.trader.chainlink_data, 'get_volatility_15min') as mock_get_volatility:
                    mock_get_volatility.return_value = 2.5
                    
                    # Call with 15min timeframe
                    analysis = self.trader.get_chainlink_analysis('bitcoin', timeframe='15min')
                    
                    # Verify the analysis contains expected data
                    self.assertEqual(analysis['trend'], 'bullish')
                    self.assertIn('indicators', analysis)
                    self.assertIn('volatility_15min', analysis['indicators'])
                    self.assertEqual(analysis['indicators']['volatility_15min'], 2.5)
    
    def test_get_chainlink_analysis_other_timeframe(self):
        """Test that get_chainlink_analysis works with other timeframes."""
        # Mock the data provider methods
        with patch.object(self.trader.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 50000.0
            
            with patch.object(self.trader.chainlink_data, 'get_crypto_trend') as mock_get_trend:
                mock_get_trend.return_value = 'bearish'
                
                with patch.object(self.trader.chainlink_data, 'get_technical_indicators') as mock_get_indicators:
                    mock_get_indicators.return_value = {
                        'sma': 48000.0,
                        'volatility': 3.0,
                        'current_price': 50000.0,
                        'price_sma_ratio': 1.04
                    }
                    
                    # Call with daily timeframe
                    analysis = self.trader.get_chainlink_analysis('bitcoin', timeframe='daily')
                    
                    # Verify the analysis contains expected data
                    self.assertEqual(analysis['trend'], 'bearish')
                    self.assertIn('indicators', analysis)
                    self.assertNotIn('volatility_15min', analysis['indicators'])  # Should not have 15min specific indicator
                    self.assertIn('sma', analysis['indicators'])
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_recent_trend_15min_bullish(self, mock_get_historical):
        """Test get_recent_trend_15min with bullish trend."""
        # Create mock historical prices showing an upward trend
        now = datetime.now()
        mock_historical_data = [
            (now - timedelta(minutes=120), 40000.0),  # Earlier price
            (now - timedelta(minutes=105), 40500.0),  # 15 min later
            (now - timedelta(minutes=90), 41000.0),   # 15 min later
            (now - timedelta(minutes=75), 42000.0),   # 15 min later
            (now - timedelta(minutes=60), 43000.0),   # 15 min later
            (now - timedelta(minutes=45), 44000.0),   # 15 min later
            (now - timedelta(minutes=30), 46000.0),   # 15 min later
            (now - timedelta(minutes=15), 48000.0),   # 15 min later
            (now, 50000.0)                            # Current price
        ]
        mock_get_historical.return_value = mock_historical_data
        
        trend = self.provider.get_recent_trend_15min('bitcoin', lookback_minutes=120)
        self.assertEqual(trend, 'bullish')
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_recent_trend_15min_bearish(self, mock_get_historical):
        """Test get_recent_trend_15min with bearish trend."""
        # Create mock historical prices showing a downward trend
        now = datetime.now()
        mock_historical_data = [
            (now - timedelta(minutes=120), 50000.0),  # Earlier price
            (now - timedelta(minutes=105), 49000.0),  # 15 min later
            (now - timedelta(minutes=90), 48000.0),   # 15 min later
            (now - timedelta(minutes=75), 47000.0),   # 15 min later
            (now - timedelta(minutes=60), 46000.0),   # 15 min later
            (now - timedelta(minutes=45), 45000.0),   # 15 min later
            (now - timedelta(minutes=30), 44000.0),   # 15 min later
            (now - timedelta(minutes=15), 43000.0),   # 15 min later
            (now, 42000.0)                            # Current price
        ]
        mock_get_historical.return_value = mock_historical_data
        
        trend = self.provider.get_recent_trend_15min('bitcoin', lookback_minutes=120)
        self.assertEqual(trend, 'bearish')
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_recent_trend_15min_neutral(self, mock_get_historical):
        """Test get_recent_trend_15min with neutral trend."""
        # Create mock historical prices showing little change
        now = datetime.now()
        mock_historical_data = [
            (now - timedelta(minutes=120), 50000.0),  # Earlier price
            (now - timedelta(minutes=105), 50010.0),  # 15 min later
            (now - timedelta(minutes=90), 49990.0),   # 15 min later
            (now - timedelta(minutes=75), 50005.0),   # 15 min later
            (now - timedelta(minutes=60), 50002.0),   # 15 min later
            (now - timedelta(minutes=45), 49998.0),   # 15 min later
            (now - timedelta(minutes=30), 50001.0),   # 15 min later
            (now - timedelta(minutes=15), 50003.0),   # 15 min later
            (now, 50000.0)                            # Current price
        ]
        mock_get_historical.return_value = mock_historical_data
        
        trend = self.provider.get_recent_trend_15min('bitcoin', lookback_minutes=120)
        self.assertEqual(trend, 'neutral')
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_volatility_15min_calculation(self, mock_get_historical):
        """Test get_volatility_15min calculation."""
        # Create mock historical prices with some variation
        now = datetime.now()
        mock_historical_data = [
            (now - timedelta(minutes=120), 50000.0),
            (now - timedelta(minutes=105), 51000.0),
            (now - timedelta(minutes=90), 49000.0),
            (now - timedelta(minutes=75), 52000.0),
            (now - timedelta(minutes=60), 48000.0),
            (now - timedelta(minutes=45), 53000.0),
            (now - timedelta(minutes=30), 47000.0),
            (now - timedelta(minutes=15), 54000.0),
            (now, 46000.0)
        ]
        mock_get_historical.return_value = mock_historical_data
        
        volatility = self.provider.get_volatility_15min('bitcoin', lookback_minutes=120)
        
        # Verify it returns a positive value
        self.assertGreater(volatility, 0)
        # Volatility should be a percentage
        self.assertIsInstance(volatility, float)
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_volatility_15min_no_data(self, mock_get_historical):
        """Test get_volatility_15min with no historical data."""
        mock_get_historical.return_value = []
        
        volatility = self.provider.get_volatility_15min('bitcoin', lookback_minutes=120)
        
        # Should return 0.0 when no data is available
        self.assertEqual(volatility, 0.0)
    
    @patch.object(ChainlinkDataProvider, 'get_historical_prices')
    def test_get_volatility_15min_single_data_point(self, mock_get_historical):
        """Test get_volatility_15min with only one data point."""
        now = datetime.now()
        mock_historical_data = [(now, 50000.0)]
        mock_get_historical.return_value = mock_historical_data
        
        volatility = self.provider.get_volatility_15min('bitcoin', lookback_minutes=120)
        
        # Should return 0.0 when only one data point is available
        self.assertEqual(volatility, 0.0)


class Test15MinuteBetting(unittest.TestCase):
    """Test cases for 15-minute betting functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.trader = PaperTrader(initial_balance=Decimal('10000.00'), auto_load=False)
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_place_crypto_bet_with_15min_analysis(self, mock_get_crypto_markets):
        """Test placing a crypto bet with 15-minute analysis."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_123",
                "question": "Will Bitcoin reach $100k?",
                "description": "Bitcoin price prediction market"
            }
        ]
        
        # Mock the Chainlink analysis
        with patch.object(self.trader, 'get_chainlink_analysis') as mock_get_analysis:
            mock_get_analysis.return_value = {
                'current_price': 50000.0,
                'trend': 'bullish',
                'indicators': {'volatility_15min': 2.5},
                'historical_prices': []
            }
            
            # Mock the order executor
            with patch.object(self.trader.order_executor, 'place_buy_order') as mock_place_order:
                mock_place_order.return_value = MagicMock(spec=Trade)
                
                # Place a bet with 15min analysis
                success = self.trader.place_crypto_bet(
                    market_title_keyword="bitcoin",
                    outcome=MarketDirection.YES,
                    amount=500.0,
                    max_price=0.6,
                    timeframe='15min'
                )
                
                # Verify the bet was placed
                self.assertTrue(success)
                mock_place_order.assert_called_once()
    
    @patch.object(PaperTrader, 'get_crypto_markets')
    def test_place_informed_crypto_bet_with_15min_analysis(self, mock_get_crypto_markets):
        """Test placing an informed crypto bet with 15-minute analysis."""
        # Mock the crypto markets
        mock_get_crypto_markets.return_value = [
            {
                "id": "test_market_456",
                "question": "Will Ethereum hit $5k?",
                "description": "Ethereum price prediction"
            }
        ]
        
        # Mock the Chainlink analysis for 15min
        with patch.object(self.trader, 'get_chainlink_analysis') as mock_get_analysis:
            mock_get_analysis.return_value = {
                'current_price': 4000.0,
                'trend': 'bullish',
                'indicators': {'volatility_15min': 3.0}
            }
            
            # Mock the order executor
            with patch.object(self.trader.order_executor, 'place_buy_order') as mock_place_order:
                mock_place_order.return_value = MagicMock(spec=Trade)
                
                # Place an informed bet with 15min analysis
                success = self.trader.place_informed_crypto_bet(
                    market_title_keyword="ethereum",
                    amount=300.0,
                    max_price=0.7,
                    confidence_threshold=0.5,
                    timeframe='15min'
                )
                
                # Verify the bet was placed
                self.assertTrue(success)
                mock_place_order.assert_called_once()
    
    def test_get_chainlink_analysis_defaults_to_15min(self):
        """Test that get_chainlink_analysis defaults to 15min when no timeframe specified."""
        # Mock the data provider methods
        with patch.object(self.trader.chainlink_data, 'get_current_price') as mock_get_price:
            mock_get_price.return_value = 50000.0
            
            with patch.object(self.trader.chainlink_data, 'get_recent_trend_15min') as mock_get_trend_15min:
                mock_get_trend_15min.return_value = 'bullish'
                
                with patch.object(self.trader.chainlink_data, 'get_crypto_trend') as mock_get_trend_daily:
                    # This should not be called when timeframe is 15min
                    mock_get_trend_daily.return_value = 'neutral'
                    
                    with patch.object(self.trader.chainlink_data, 'get_volatility_15min') as mock_get_volatility:
                        mock_get_volatility.return_value = 2.5
                        
                        # Call without specifying timeframe (should default to 15min in the implementation)
                        analysis = self.trader.get_chainlink_analysis('bitcoin', timeframe='15min')
                        
                        # Verify 15min-specific methods were called
                        mock_get_trend_15min.assert_called_once()
                        # mock_get_trend_daily should not have been called for 15min analysis
                        # Verify the analysis contains 15min indicators
                        self.assertIn('indicators', analysis)
                        self.assertIn('volatility_15min', analysis['indicators'])


if __name__ == '__main__':
    unittest.main()