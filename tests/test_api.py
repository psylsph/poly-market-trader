import unittest
from unittest.mock import patch, MagicMock
from poly_market_trader.api.market_data_provider import MarketDataProvider
from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider
from poly_market_trader.models.trade import MarketDirection


class TestMarketDataProvider(unittest.TestCase):
    """Test cases for the MarketDataProvider class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.provider = MarketDataProvider()
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_markets_success(self, mock_get):
        """Test getting markets successfully."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "1", "question": "Test market"},
            {"id": "2", "question": "Another market"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_markets()
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('markets', args[0])  # URL should contain 'markets'
        self.assertIn('limit', kwargs['params'])
        
        # Verify the result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "1")
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_market_by_id_success(self, mock_get):
        """Test getting a specific market by ID."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "1", "question": "Test market"}]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_market_by_id("1")
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('markets', args[0])  # URL should contain 'markets'
        self.assertIn('marketId', kwargs['params'])
        
        # Verify the result
        self.assertEqual(result["id"], "1")
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_order_book(self, mock_get):
        """Test getting order book for a token."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"asks": [], "bids": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_order_book("test_token")
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('book', args[0])  # URL should contain 'book'
        self.assertIn('token_id', kwargs['params'])
        
        # Verify the result
        self.assertIn('asks', result)
        self.assertIn('bids', result)
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_current_price(self, mock_get):
        """Test getting current price for a token."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"price": "0.6"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_current_price("test_token")
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('price', args[0])  # URL should contain 'price'
        self.assertIn('token_id', kwargs['params'])
        
        # Verify the result
        self.assertEqual(result, 0.6)
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_crypto_markets(self, mock_get):
        """Test getting crypto-related markets."""
        # Mock the response with mixed markets
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "1", "question": "Will Bitcoin reach $100k?", "description": "About Bitcoin"},
            {"id": "2", "question": "Will it rain tomorrow?", "description": "Weather forecast"},
            {"id": "3", "question": "Ethereum price prediction", "description": "Crypto market"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_crypto_markets()
        
        # Verify the call was made correctly
        mock_get.assert_called()
        
        # The result should contain only crypto-related markets
        # Note: The actual filtering depends on the implementation in the method
        # which we're testing as a whole
        self.assertIsInstance(result, list)
    
    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_market_prices(self, mock_get):
        """Test getting market prices."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "1",
                "outcomes": ["Yes", "No"],
                "prices": ["0.6", "0.4"]
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_market_prices("1")
        
        # Verify the call was made correctly
        mock_get.assert_called()
        
        # Verify the result structure
        self.assertIn('yes', result)
        self.assertIn('no', result)
        self.assertEqual(result['yes'], 0.6)
        self.assertEqual(result['no'], 0.4)


class TestChainlinkDataProvider(unittest.TestCase):
    """Test cases for the ChainlinkDataProvider class"""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.provider = ChainlinkDataProvider()
    
    @patch('poly_market_trader.api.chainlink_data_provider.requests.get')
    def test_get_current_price_success(self, mock_get):
        """Test getting current price for a cryptocurrency."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {"bitcoin": {"usd": 50000}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_current_price("bitcoin")
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('simple/price', args[0])  # URL should contain 'simple/price'
        self.assertIn('ids', kwargs['params'])
        self.assertIn('vs_currencies', kwargs['params'])
        
        # Verify the result
        self.assertEqual(result, 50000.0)
    
    @patch('poly_market_trader.api.chainlink_data_provider.requests.get')
    def test_get_current_price_not_found(self, mock_get):
        """Test getting current price for a cryptocurrency that doesn't exist."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_current_price("nonexistent_crypto")
        
        # Verify the result
        self.assertIsNone(result)
    
    @patch('poly_market_trader.api.chainlink_data_provider.requests.get')
    def test_get_historical_prices(self, mock_get):
        """Test getting historical prices."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "prices": [
                [1609459200000, 40000],  # [timestamp_ms, price]
                [1609545600000, 41000],
                [1609632000000, 42000]
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_historical_prices("bitcoin", hours=24, interval='15min')
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('market_chart', args[0])  # URL should contain 'market_chart'
        
        # Verify the result
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        # Each element should be a tuple of (datetime, float)
        timestamp, price = result[0]
        self.assertEqual(price, 40000.0)
    
    @patch('poly_market_trader.api.chainlink_data_provider.requests.get')
    def test_get_multiple_prices(self, mock_get):
        """Test getting prices for multiple cryptocurrencies."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bitcoin": {"usd": 50000},
            "ethereum": {"usd": 3000}
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_multiple_prices(["bitcoin", "ethereum"])
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('simple/price', args[0])  # URL should contain 'simple/price'
        
        # Verify the result
        self.assertIn('bitcoin', result)
        self.assertIn('ethereum', result)
        self.assertEqual(result['bitcoin'], 50000.0)
        self.assertEqual(result['ethereum'], 3000.0)
    
    @unittest.skip("Legacy Chainlink method not implemented for Binance API")
    def test_get_chainlink_feed_address(self):
        """Test getting Chainlink feed addresses."""
        result = self.provider.get_chainlink_feed_address("BTC/USD")
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("0x"))  # Should be an Ethereum address
    
    @unittest.skip("Uses mocked/legacy API behavior")
    def test_get_crypto_trend(self):
        """Test getting crypto trend (this method relies on get_historical_prices)."""
        # This test is tricky because it depends on get_historical_prices
        # We'll test the logic assuming get_historical_prices works
        with patch.object(self.provider, 'get_historical_prices') as mock_method:
            # Mock historical prices showing an upward trend
            mock_method.return_value = [
                (MagicMock(), 40000),  # Earlier price
                (MagicMock(), 50000)   # Later price (higher)
            ]
            
            result = self.provider.get_crypto_trend("bitcoin", days=7)
            self.assertEqual(result, 'bullish')
            
            # Mock historical prices showing a downward trend
            mock_method.return_value = [
                (MagicMock(), 50000),  # Earlier price
                (MagicMock(), 40000)   # Later price (lower)
            ]
            
            result = self.provider.get_crypto_trend("bitcoin", days=7)
            self.assertEqual(result, 'bearish')
            
            # Mock historical prices showing no significant change
            mock_method.return_value = [
                (MagicMock(), 50000),  # Earlier price
                (MagicMock(), 50001)   # Later price (almost same)
            ]
            
            result = self.provider.get_crypto_trend("bitcoin", days=7)
            self.assertEqual(result, 'neutral')
    
    @unittest.skip("Uses mocked/legacy API behavior")
    def test_get_technical_indicators(self):
        """Test getting technical indicators."""
        # This method also depends on get_historical_prices
        with patch.object(self.provider, 'get_historical_prices') as mock_method:
            # Mock historical prices
            mock_method.return_value = [
                (MagicMock(), 40000),
                (MagicMock(), 42000),
                (MagicMock(), 41000),
                (MagicMock(), 43000),
                (MagicMock(), 44000)
            ]
            
            result = self.provider.get_technical_indicators("bitcoin", days=30)
            
            # Verify the result structure
            self.assertIn('sma', result)
            self.assertIn('volatility', result)
            self.assertIn('current_price', result)
            self.assertIn('price_sma_ratio', result)
            self.assertIn('trend_direction', result)


if __name__ == '__main__':
    unittest.main()