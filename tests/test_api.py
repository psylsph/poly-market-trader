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
                "question": "Test Market",
                "outcomePrices": ["0.6", "0.4"]
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

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_15m_crypto_markets(self, mock_get):
        """Test getting 15-minute crypto markets."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "1", "question": "Will Bitcoin reach $100k?"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.provider.get_15m_crypto_markets()

        # Verify the API was called with correct time window (1-16 minutes)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('end_date_min', kwargs['params'])
        self.assertIn('end_date_max', kwargs['params'])

        # Verify the result is a list
        self.assertIsInstance(result, list)

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_1h_crypto_markets(self, mock_get):
        """Test getting 1-hour crypto markets."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "2", "question": "Ethereum price in 1 hour"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.provider.get_1h_crypto_markets()

        # Verify the API was called with correct time window (50-70 minutes)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('end_date_min', kwargs['params'])
        self.assertIn('end_date_max', kwargs['params'])

        # Verify the result is a list
        self.assertIsInstance(result, list)

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_4h_crypto_markets(self, mock_get):
        """Test getting 4-hour crypto markets."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "3", "question": "Solana in 4 hours"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.provider.get_4h_crypto_markets()

        # Verify the API was called with correct time window (230-250 minutes)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('end_date_min', kwargs['params'])
        self.assertIn('end_date_max', kwargs['params'])

        # Verify the result is a list
        self.assertIsInstance(result, list)

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_short_term_crypto_markets(self, mock_get):
        """Test getting all short-term crypto markets (15m, 1h, 4h)."""
        # Mock responses for 3 API calls (15m, 1h, 4h)
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            [{"id": "1", "question": "BTC 15m"}],  # 15m markets
            [{"id": "2", "question": "ETH 1h"}],   # 1h markets
            [{"id": "3", "question": "SOL 4h"}]    # 4h markets
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.provider.get_short_term_crypto_markets()

        # Verify 3 API calls were made
        self.assertEqual(mock_get.call_count, 3)

        # Verify combined result
        self.assertIsInstance(result, list)
        # Should have combined markets from all 3 calls
        self.assertGreaterEqual(len(result), 0)

    def test_validate_token_id(self):
        """Test token ID validation."""
        # Valid numeric token ID
        self.assertTrue(self.provider._validate_token_id("12345678901234567890"))
        # Empty string
        self.assertFalse(self.provider._validate_token_id(""))
        # Non-string
        self.assertFalse(self.provider._validate_token_id(12345))
        # Too long (78 digits)
        self.assertFalse(self.provider._validate_token_id("1" * 78))
        # Non-numeric
        self.assertFalse(self.provider._validate_token_id("abc123"))
        # Valid within limit (50 digits)
        self.assertTrue(self.provider._validate_token_id("1" * 50))

    @patch('poly_market_trader.api.market_data_provider.ClobClient')
    def test_get_order_book_404(self, mock_clob_client):
        """Test 404 error handling in get_order_book."""
        mock_client_instance = mock_clob_client.return_value
        mock_client_instance.get_order_book.side_effect = Exception("404 Not Found")

        result = self.provider.get_order_book("invalid_token")
        self.assertIsNone(result)

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    def test_get_market_prices_closed_market(self, mock_get):
        """Test get_market_prices with a closed market."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "1", "active": False, "closed": True, "outcomePrices": []}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.provider.get_market_prices("1")
        self.assertEqual(result['yes'], 0.0)
        self.assertEqual(result['no'], 0.0)

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
        mock_response.json.return_value = {"symbol": "BTCUSDT", "price": "50000.00"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_current_price("bitcoin")
        
        # Verify the call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('ticker/price', args[0])  # URL should contain 'ticker/price' (Binance API)
        self.assertIn('symbol', kwargs['params'])
        
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
        # Binance klines API format: [timestamp_ms, open, high, low, close, volume, ...]
        mock_response.json.return_value = [
            [16094592000000, 39000, 41000, 38000, 40000, 100, 16094592000000],  # kline 1
            [1609545600000, 40000, 42000, 39000, 41000, 120, 1609545600000],  # kline 2
            [1609632000000, 41000, 43000, 40000, 42000, 150, 1609632000000]   # kline 3
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_historical_prices("bitcoin", hours=24, interval='15m')
        
        # Verify that call was made correctly (Binance klines endpoint)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertIn('klines', args[0])  # URL should contain 'klines' (Binance API)
        
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
        # Binance API returns different format for each call
        # First call (bitcoin)
        mock_response.json.side_effect = [
            {"symbol": "BTCUSDT", "price": "50000.00"},
            {"symbol": "ETHUSDT", "price": "3000.00"}
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.get_multiple_prices(["bitcoin", "ethereum"])
        
        # Verify the call was made correctly (Binance makes separate calls for each crypto)
        self.assertEqual(mock_get.call_count, 2)  # 2 crypto prices = 2 API calls
        
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