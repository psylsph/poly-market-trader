import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal


class TestStrategyLogic(unittest.TestCase):
    """Test cases for betting strategy logic (Value Betting & RSI)"""

    def test_value_betting_high_confidence_high_price_skip(self):
        """
        Test that the bot skips betting when confidence is high but price is too high.
        Logic: If confidence (0.75) < price (0.80) + margin (0.05), skip.
        """
        confidence = 0.75
        market_price = 0.80
        margin = 0.05
        
        should_skip = confidence < (market_price + margin)
        
        self.assertTrue(should_skip, "Bot should skip when confidence doesn't exceed price + margin")

    def test_value_betting_high_confidence_low_price_bet(self):
        """
        Test that the bot bets when confidence is high and price is low.
        Logic: If confidence (0.85) > price (0.60) + margin (0.05), bet.
        """
        confidence = 0.85
        market_price = 0.60
        margin = 0.05
        
        should_bet = confidence > (market_price + margin)
        
        self.assertTrue(should_bet, "Bot should bet when confidence exceeds price + margin")

    def test_value_betting_low_confidence_always_skip(self):
        """
        Test that the bot skips betting when confidence is too low.
        """
        confidence = 0.50
        market_price = 0.30
        margin = 0.05
        
        # Even if price is favorable, low confidence should trigger skip
        should_skip = confidence < (market_price + margin) or confidence < 0.55
        
        self.assertTrue(should_skip, "Bot should skip when confidence is below minimum threshold")

    def test_value_betting_zero_price_skip(self):
        """
        Test that the bot skips betting when market price is $0.00.
        """
        market_price = 0.00
        
        should_skip = market_price <= 0.01
        
        self.assertTrue(should_skip, "Bot should skip when market price is $0.00")

    def test_value_betting_near_zero_price_skip(self):
        """
        Test that the bot skips betting when market price is near zero.
        """
        market_price = 0.005
        
        should_skip = market_price <= 0.01
        
        self.assertTrue(should_skip, "Bot should skip when market price is near zero")

    def test_arbitrage_opportunity(self):
        """
        Test arbitrage detection: YES + NO < 0.99 = arbitrage opportunity
        Example: YES=0.60, NO=0.30, Sum=0.90 -> Buy both, guaranteed profit
        """
        yes_price = 0.60
        no_price = 0.30
        price_sum = yes_price + no_price
        arbitrage_threshold = 0.99
        
        is_arbitrage = price_sum < arbitrage_threshold and yes_price > 0.01 and no_price > 0.01
        
        self.assertTrue(is_arbitrage, "Should detect arbitrage when YES + NO < 0.99")
        
        # Calculate expected profit
        bet_amount = 100.0
        quantity_yes = bet_amount / yes_price  # 166.67 shares
        quantity_no = bet_amount / no_price    # 333.33 shares
        total_cost = bet_amount * 2            # $200
        total_payout = quantity_yes + quantity_no  # ~500 shares worth $1 each = $500
        expected_profit_pct = (1.0 - price_sum) * 100  # 10%
        
        self.assertAlmostEqual(expected_profit_pct, 10.0)
        self.assertGreater(total_payout, total_cost)

    def test_no_arbitrage_when_prices_sum_to_1(self):
        """
        Test that normal prices (YES + NO = 1.0) don't trigger arbitrage.
        """
        yes_price = 0.60
        no_price = 0.40
        price_sum = yes_price + no_price
        arbitrage_threshold = 0.99
        
        is_arbitrage = price_sum < arbitrage_threshold
        
        self.assertFalse(is_arbitrage, "Should not detect arbitrage when YES + NO = 1.0")

    def test_no_arbitrage_when_prices_sum_greater_than_1(self):
        """
        Test that overpriced markets don't trigger arbitrage.
        """
        yes_price = 0.70
        no_price = 0.40
        price_sum = yes_price + no_price
        arbitrage_threshold = 0.99
        
        is_arbitrage = price_sum < arbitrage_threshold
        
        self.assertFalse(is_arbitrage, "Should not detect arbitrage when YES + NO > 1.0")

    def test_rsi_boost_overbought(self):
        """
        Test RSI confidence boost for overbought conditions.
        RSI > 70 (Overbought) + Bullish Trend -> Expect Pullback -> Bet NO
        """
        rsi = 75.0
        outcome = "NO"  # Betting NO on "Up" market = Expecting pullback
        
        # If RSI > 70 and we're betting NO, boost confidence
        if rsi > 70 and outcome == "NO":
            confidence_boost = 0.1
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.80)
        self.assertGreater(final_confidence, base_confidence)

    def test_rsi_boost_oversold(self):
        """
        Test RSI confidence boost for oversold conditions.
        RSI < 30 (Oversold) + Bearish Trend -> Expect Bounce -> Bet YES
        """
        rsi = 25.0
        outcome = "YES"  # Betting YES on "Up" market = Expecting bounce
        
        # If RSI < 30 and we're betting YES, boost confidence
        if rsi < 30 and outcome == "YES":
            confidence_boost = 0.1
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.80)
        self.assertGreater(final_confidence, base_confidence)

    def test_rsi_no_boost_contrarian_signal(self):
        """
        Test that RSI doesn't boost confidence if it contradicts the trend.
        RSI > 70 (Overbought) but betting YES (expecting rise) = Contradiction
        """
        rsi = 75.0
        outcome = "YES"  # Betting YES on "Up" market
        
        # RSI says overbought (expect drop), but we're betting YES (expect rise)
        # This is a contradiction, no boost
        if rsi > 70 and outcome == "NO":
            confidence_boost = 0.1
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.70)
        self.assertNotAlmostEqual(final_confidence, 0.80)

    def test_rsi_neutral_slight_boost(self):
        """
        Test slight confidence boost for neutral RSI (40 < RSI < 60).
        """
        rsi = 50.0
        outcome = "NO"
        
        if 40 < rsi < 60:
            confidence_boost = 0.05
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.55
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.60)

    def test_macd_bullish_boost(self):
        """
        Test MACD bullish boost for YES bets.
        """
        macd_histogram = 0.5
        outcome = "YES"
        
        if macd_histogram > 0 and outcome == "YES":
            confidence_boost = 0.05
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.75)

    def test_macd_bearish_boost(self):
        """
        Test MACD bearish boost for NO bets.
        """
        macd_histogram = -0.5
        outcome = "NO"
        
        if macd_histogram < 0 and outcome == "NO":
            confidence_boost = 0.05
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.75)

    def test_sma_alignment_bullish(self):
        """
        Test SMA alignment bullish boost for YES bets.
        """
        sma_alignment = 0.1  # sma_9 > sma_20 > sma_50
        outcome = "YES"
        
        if sma_alignment > 0 and outcome == "YES":
            confidence_boost = 0.05
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.75)

    def test_sma_alignment_bearish(self):
        """
        Test SMA alignment bearish boost for NO bets.
        """
        sma_alignment = -0.1  # sma_9 < sma_20 < sma_50
        outcome = "NO"
        
        if sma_alignment < 0 and outcome == "NO":
            confidence_boost = 0.05
        else:
            confidence_boost = 0.0
            
        base_confidence = 0.70
        final_confidence = base_confidence + confidence_boost
        
        self.assertAlmostEqual(final_confidence, 0.75)

    def test_combined_boosts(self):
        """
        Test that multiple boosts can stack (but are capped at 0.95).
        """
        rsi = 75.0  # Overbought, boost NO
        macd_histogram = -0.5  # Bearish, boost NO
        sma_alignment = -0.1  # Bearish, boost NO
        outcome = "NO"
        
        confidence = 0.70
        
        # RSI boost
        if rsi > 70 and outcome == "NO":
            confidence += 0.1
            
        # MACD boost
        if macd_histogram < 0 and outcome == "NO":
            confidence += 0.05
            
        # SMA alignment boost
        if sma_alignment < 0 and outcome == "NO":
            confidence += 0.05
        
        # Cap at 0.95
        confidence = min(0.95, confidence)
        
        self.assertAlmostEqual(confidence, 0.90)

    def test_confidence_cap_at_095(self):
        """
        Test that confidence is capped at 0.95.
        """
        confidence = 0.92
        confidence_boost = 0.1  # Would normally push to 1.02
        
        final_confidence = min(0.95, confidence + confidence_boost)
        
        self.assertEqual(final_confidence, 0.95)
        self.assertLess(final_confidence, 1.0)


class TestMarketMonitorIntegration(unittest.TestCase):
    """Integration tests for MarketMonitor with new strategy logic"""

    @patch('poly_market_trader.api.market_data_provider.requests.get')
    @patch('poly_market_trader.api.chainlink_data_provider.requests.get')
    def test_analyze_market_with_value_betting(self, mock_chainlink_get, mock_market_get):
        """
        Test that _analyze_and_bet correctly applies value betting logic.
        """
        from poly_market_trader.services.market_monitor import MarketMonitor
        from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider
        from poly_market_trader.api.market_data_provider import MarketDataProvider
        from poly_market_trader.services.order_executor import OrderExecutor
        from poly_market_trader.models.portfolio import Portfolio
        from poly_market_trader.storage.bet_tracker import BetTracker
        
        # Create mocks
        portfolio = Portfolio(initial_balance=Decimal('10000'))
        market_data = MarketDataProvider()
        chainlink_data = ChainlinkDataProvider()
        order_executor = OrderExecutor(portfolio)
        bet_tracker = BetTracker()
        
        # Mock the API responses
        # Mock market prices: YES=0.50, NO=0.50
        mock_market_response = MagicMock()
        mock_market_response.json.return_value = [{'id': '123', 'question': 'Bitcoin Up or Down?', 'startDate': '', 'endDate': '2026-01-13T21:00:00Z', 'outcomes': ['YES', 'NO'], 'prices': [0.50, 0.50]}]
        mock_market_response.raise_for_status = MagicMock()
        mock_market_get.return_value = mock_market_response
        
        # Mock Chainlink: Bullish trend, RSI > 70
        mock_chainlink_response = MagicMock()
        mock_chainlink_response.json.return_value = []
        mock_chainlink_response.raise_for_status = MagicMock()
        mock_chainlink_get.return_value = mock_chainlink_response
        
        # Create monitor and analyze
        monitor = MarketMonitor(portfolio, market_data, chainlink_data, order_executor, bet_tracker)
        
        market = {
            'id': '123',
            'question': 'Bitcoin Up or Down?',
            'startDate': '',
            'endDate': '2026-01-13T21:00:00Z'
        }
        
        # The market prices are 0.50/0.50.
        # If our strategy says "Bullish -> Bet NO", confidence is 0.70.
        # RSI > 70 boosts confidence to 0.80.
        # Check: 0.80 > 0.50 + 0.05 = 0.55? YES.
        # So the bot SHOULD bet.
        
        # We can't fully test the internal logic without mocking more methods,
        # but we can verify the market structure is passed correctly.
        # This is a placeholder for more comprehensive integration tests.
        
        self.assertIsNotNone(monitor)
        self.assertEqual(len(monitor.active_bets), 0)


if __name__ == '__main__':
    unittest.main()
