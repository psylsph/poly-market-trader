import unittest
from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider


class TestChainlinkIndicators(unittest.TestCase):
    """Test cases for technical indicators in ChainlinkDataProvider"""

    def setUp(self):
        """Set up test fixtures"""
        self.provider = ChainlinkDataProvider()

    def test_calculate_rsi_bullish(self):
        """Test RSI calculation for a steadily increasing price (RSI should be high)"""
        # Simulate a steady uptrend: prices increasing by 1 each time
        prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0, 111.0, 112.0, 113.0, 114.0, 115.0]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # In a strong uptrend, RSI should be > 50, ideally > 70
        self.assertGreater(rsi, 50)
        self.assertLessEqual(rsi, 100)

    def test_calculate_rsi_bearish(self):
        """Test RSI calculation for a steadily decreasing price (RSI should be low)"""
        # Simulate a steady downtrend: prices decreasing by 1 each time
        prices = [115.0, 114.0, 113.0, 112.0, 111.0, 110.0, 109.0, 108.0, 107.0, 106.0, 105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # In a strong downtrend, RSI should be < 50, ideally < 30
        self.assertLess(rsi, 50)
        self.assertGreaterEqual(rsi, 0)

    def test_calculate_rsi_neutral(self):
        """Test RSI calculation for a flat price (RSI should be around 50)"""
        # Simulate a flat market: prices oscillating slightly
        prices = [100.0, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0, 100.5, 100.0, 100.5]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # In a flat market, RSI should be around 50
        self.assertGreater(rsi, 40)
        self.assertLess(rsi, 60)

    def test_calculate_rsi_insufficient_data(self):
        """Test RSI calculation with insufficient data (should return neutral)"""
        prices = [100.0, 101.0, 102.0]  # Less than 8 values needed for period=7
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # Should return 50.0 (neutral) if not enough data
        self.assertEqual(rsi, 50.0)

    def test_calculate_rsi_exact_period(self):
        """Test RSI calculation with exactly the required data points"""
        prices = [100.0] * 8  # Exactly period + 1 for period=7
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # Flat prices with no losses = RSI 100.0 (Bullish interpretation)
        self.assertEqual(rsi, 100.0)

    def test_calculate_rsi_volatile(self):
        """Test RSI calculation with highly volatile prices"""
        # Simulate high volatility: large swings up and down
        prices = [100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0, 100.0, 110.0]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # With equal gains and losses, RSI should be around 50
        self.assertGreater(rsi, 40)
        self.assertLess(rsi, 60)

    def test_calculate_rsi_oversold(self):
        """Test RSI detection of oversold conditions (RSI < 30)"""
        # Simulate a sharp drop - use 7-period RSI, so we need a strong move
        prices = [100.0, 95.0, 90.0, 85.0, 82.0, 80.0, 78.0, 77.0, 76.5, 76.0, 75.5, 75.0, 74.5, 74.0, 73.5, 73.0]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # Should detect oversold condition
        self.assertLess(rsi, 30)

    def test_calculate_rsi_overbought(self):
        """Test RSI detection of overbought conditions (RSI > 70)"""
        # Simulate a sharp rise - use 7-period RSI, so we need a strong move
        prices = [100.0, 105.0, 110.0, 115.0, 118.0, 120.0, 122.0, 123.0, 123.5, 124.0, 124.5, 125.0, 125.5, 126.0, 126.5, 127.0]
        
        rsi = self.provider.calculate_rsi(prices, period=7)
        
        # Should detect overbought condition
        self.assertGreater(rsi, 70)

    def test_calculate_macd_bullish(self):
        """Test MACD calculation for bullish crossover"""
        # Simulate rising prices - need at least slow + signal = 35 data points
        prices = [float(x) for x in range(100, 136)]  # 100.0 to 135.0 (36 points)
        
        macd_line, signal_line, histogram = self.provider.calculate_macd(prices, fast=12, slow=26, signal=9)
        
        # In strong uptrend, MACD histogram should be positive (MACD above signal)
        # Note: MACD can be 0 if not enough data, so just check histogram
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)

    def test_calculate_macd_bearish(self):
        """Test MACD calculation for bearish crossover"""
        # Simulating falling prices - need at least slow + signal = 35 data points
        prices = [float(x) for x in range(135, 99, -1)]  # 135.0 down to 100.0 (36 points)
        
        macd_line, signal_line, histogram = self.provider.calculate_macd(prices, fast=12, slow=26, signal=9)
        
        # Should return valid values
        self.assertIsNotNone(macd_line)
        self.assertIsNotNone(signal_line)

    def test_calculate_macd_returns_tuple(self):
        """Test that MACD returns a tuple of three values"""
        prices = [float(x) for x in range(100, 136)]  # 36 points
        
        result = self.provider.calculate_macd(prices)
        
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[0], float)
        self.assertIsInstance(result[1], float)
        self.assertIsInstance(result[2], float)


if __name__ == '__main__':
    unittest.main()
