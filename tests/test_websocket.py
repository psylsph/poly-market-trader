"""Tests for WebSocket functionality in Polymarket Paper Trader"""
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import json
from datetime import datetime
from collections import deque

from poly_market_trader.api.websocket_client import PolymarketWebSocketClient, FastMarketMonitor
from poly_market_trader.models.portfolio import Portfolio
from poly_market_trader.services.order_executor import OrderExecutor
from decimal import Decimal


class TestPolymarketWebSocketClient(unittest.TestCase):
    """Test cases for the PolymarketWebSocketClient class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.client = PolymarketWebSocketClient()

    def test_initialization(self):
        """Test that WebSocket client initializes correctly."""
        self.assertFalse(self.client.is_connected)
        self.assertEqual(self.client.reconnect_count, 0)
        self.assertEqual(self.client.subscribed_markets, set())
        self.assertIsInstance(self.client.market_data, dict)
        self.assertIsInstance(self.client.price_history, dict)

    def test_connect_success(self):
        """Test successful WebSocket connection."""
        # Create an async mock that returns a mock WebSocket
        async def mock_connect_coro():
            mock_ws = MagicMock()
            return mock_ws

        with patch('poly_market_trader.api.websocket_client.websockets.connect',
                   return_value=mock_connect_coro()):
            # Run the async connect method
            async def run_test():
                result = await self.client.connect()
                self.assertTrue(result)
                self.assertTrue(self.client.is_connected)
                self.assertEqual(self.client.reconnect_count, 0)

            asyncio.run(run_test())

    @patch('poly_market_trader.api.websocket_client.websockets.connect')
    def test_connect_failure(self, mock_connect):
        """Test WebSocket connection failure."""
        # Mock connection failure
        mock_connect.side_effect = Exception("Connection failed")

        # Run the async connect method
        async def run_test():
            result = await self.client.connect()
            self.assertFalse(result)
            self.assertFalse(self.client.is_connected)

        asyncio.run(run_test())

    def test_subscribe_markets_not_connected(self):
        """Test subscribing to markets when not connected."""
        async def run_test():
            result = await self.client.subscribe_markets(["token1", "token2"])
            self.assertFalse(result)

        asyncio.run(run_test())

    def test_get_market_price_empty(self):
        """Test getting price for non-existent market."""
        result = self.client.get_market_price("nonexistent_token")
        self.assertIsNone(result)

    def test_get_all_prices_empty(self):
        """Test getting all prices when no data exists."""
        result = self.client.get_all_prices()
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 0)

    def test_process_single_message_price_update(self):
        """Test processing a single price update message."""
        # Test data with nested 'yes'/'no' dicts
        message_data = {
            'type': 'book',
            'asset_id': 'test_token_123',
            'yes': {'best_bid': 0.60, 'best_ask': 0.62},
            'no': {'best_bid': 0.38, 'best_ask': 0.40}
        }

        async def run_test():
            await self.client._process_single_message(message_data)

            # Check that price was stored
            price_data = self.client.get_market_price('test_token_123')
            self.assertIsNotNone(price_data)
            self.assertEqual(price_data['yes_bid'], 0.60)
            self.assertEqual(price_data['yes_ask'], 0.62)
            self.assertEqual(price_data['yes_mid'], 0.61)
            self.assertEqual(price_data['no_bid'], 0.38)
            self.assertEqual(price_data['no_ask'], 0.40)
            self.assertEqual(price_data['no_mid'], 0.39)

        asyncio.run(run_test())

    def test_process_single_message_flat_format(self):
        """Test processing a price update message with flat format."""
        # Test data with flat 'yes_bid'/'yes_ask' fields
        message_data = {
            'type': 'price_change',
            'token_id': 'test_token_456',
            'yes_bid': 0.55,
            'yes_ask': 0.57,
            'no_bid': 0.43,
            'no_ask': 0.45
        }

        async def run_test():
            await self.client._process_single_message(message_data)

            # Check that price was stored
            price_data = self.client.get_market_price('test_token_456')
            self.assertIsNotNone(price_data)
            self.assertEqual(price_data['yes_mid'], 0.56)
            self.assertEqual(price_data['no_mid'], 0.44)

        asyncio.run(run_test())

    def test_handle_message_list(self):
        """Test handling a list of messages."""
        messages = [
            {'type': 'book', 'asset_id': 'token1', 'yes': {'best_bid': 0.5, 'best_ask': 0.52}},
            {'type': 'book', 'asset_id': 'token2', 'yes': {'best_bid': 0.6, 'best_ask': 0.62}}
        ]

        async def run_test():
            await self.client._handle_message(json.dumps(messages))

            # Check both prices were stored
            price1 = self.client.get_market_price('token1')
            price2 = self.client.get_market_price('token2')
            self.assertIsNotNone(price1)
            self.assertIsNotNone(price2)

        asyncio.run(run_test())

    def test_handle_message_invalid_json(self):
        """Test handling invalid JSON message."""
        # Should not raise an exception
        async def run_test():
            await self.client._handle_message("invalid json{{")

        asyncio.run(run_test())

    def test_price_history_tracking(self):
        """Test that price history is tracked correctly."""
        message_data = {
            'type': 'book',
            'asset_id': 'test_token_history',
            'yes': {'best_bid': 0.50, 'best_ask': 0.52},
            'no': {'best_bid': 0.48, 'best_ask': 0.50}
        }

        async def run_test():
            # Send multiple updates
            for i in range(5):
                await self.client._process_single_message(message_data)

            # Check price history
            self.assertIn('test_token_history', self.client.price_history)
            self.assertEqual(len(self.client.price_history['test_token_history']), 5)

        asyncio.run(run_test())

    def test_arbitrage_detection(self):
        """Test arbitrage opportunity detection."""
        # Track if callback was triggered
        arbitrage_triggered = []
        arbitrage_info = {}

        def arbitrage_callback(info):
            arbitrage_triggered.append(True)
            arbitrage_info.update(info)

        self.client.on_arbitrage = arbitrage_callback

        # Price data with arbitrage opportunity (YES + NO < 0.99)
        message_data = {
            'type': 'book',
            'asset_id': 'arb_token',
            'yes': {'best_bid': 0.48, 'best_ask': 0.50},
            'no': {'best_bid': 0.40, 'best_ask': 0.42}
        }
        # yes_mid = 0.49, no_mid = 0.41, sum = 0.90 < 0.99

        async def run_test():
            await self.client._process_single_message(message_data)

            # Check that arbitrage was detected
            self.assertTrue(len(arbitrage_triggered) > 0)
            self.assertEqual(arbitrage_info['token_id'], 'arb_token')
            self.assertGreater(arbitrage_info['profit'], 0)

        asyncio.run(run_test())


class TestFastMarketMonitor(unittest.TestCase):
    """Test cases for the FastMarketMonitor class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.portfolio = Portfolio(initial_balance=Decimal('10000.00'))
        self.order_executor = OrderExecutor(self.portfolio)
        self.monitor = FastMarketMonitor(
            portfolio=self.portfolio,
            order_executor=self.order_executor
        )

    def test_initialization(self):
        """Test that FastMarketMonitor initializes correctly."""
        self.assertFalse(self.monitor.is_running)
        self.assertEqual(self.monitor.arbitrage_threshold, 0.99)
        self.assertEqual(self.monitor.min_profit_threshold, 1.0)
        self.assertIsInstance(self.monitor.bet_history, set)
        self.assertIsInstance(self.monitor.token_to_market, dict)

    def test_find_market_for_token_empty_cache(self):
        """Test finding market when cache is empty."""
        result = self.monitor._find_market_for_token('unknown_token')
        self.assertIsNone(result)

    def test_handle_arbitrage_insufficient_balance(self):
        """Test arbitrage handling with insufficient balance."""
        # Set portfolio to very low balance
        self.portfolio.update_balance(Decimal('-9990'))  # Only $10 left

        arbitrage_info = {
            'token_id': 'test_token',
            'yes_price': 0.48,
            'no_price': 0.42,
            'sum': 0.90,
            'profit': 10.0
        }

        self.monitor._handle_arbitrage(arbitrage_info)

        # Should skip due to insufficient balance
        # (bet_amount would be 10% of $10 = $1, which is < $10 minimum)
        self.assertIn('test_token', self.monitor.bet_history)

    def test_handle_arbitrage_no_market_found(self):
        """Test arbitrage handling when market can't be found."""
        # Empty token_to_market mapping
        self.monitor.token_to_market = {}

        arbitrage_info = {
            'token_id': 'unknown_token',
            'yes_price': 0.48,
            'no_price': 0.42,
            'sum': 0.90,
            'profit': 10.0
        }

        self.monitor._handle_arbitrage(arbitrage_info)

        # Should skip due to no market found
        self.assertIn('unknown_token', self.monitor.bet_history)

    def test_handle_arbitrage_below_profit_threshold(self):
        """Test arbitrage handling with profit below threshold."""
        self.monitor.min_profit_threshold = 5.0  # Require 5% profit

        arbitrage_info = {
            'token_id': 'test_token',
            'yes_price': 0.48,
            'no_price': 0.50,
            'sum': 0.98,
            'profit': 2.0  # Only 2% profit
        }

        self.monitor._handle_arbitrage(arbitrage_info)

        # Should not trigger callback due to low profit
        # But still add to bet_history to avoid reprocessing
        # Actually, looking at the code, it returns early without adding to bet_history
        # if profit is below threshold
        self.assertNotIn('test_token', self.monitor.bet_history)

    def test_handle_arbitrage_duplicate(self):
        """Test that duplicate arbitrage opportunities are skipped."""
        # Add token to bet_history
        self.monitor.bet_history.add('duplicate_token')

        arbitrage_info = {
            'token_id': 'duplicate_token',
            'yes_price': 0.48,
            'no_price': 0.42,
            'sum': 0.90,
            'profit': 10.0
        }

        self.monitor._handle_arbitrage(arbitrage_info)

        # Should return early without attempting to place bets
        # No assertion needed, just verify no exception is raised


class TestPaperTraderWebSocketIntegration(unittest.TestCase):
    """Test cases for PaperTrader WebSocket integration"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        from poly_market_trader.services.paper_trader import PaperTrader
        self.trader = PaperTrader(auto_load=False)

    def test_initialization(self):
        """Test that PaperTrader WebSocket attributes initialize correctly."""
        self.assertIsNone(self.trader.ws_client)
        self.assertIsNone(self.trader.ws_monitor)
        self.assertIsNone(self.trader.ws_loop)
        self.assertIsNone(self.trader.ws_thread)
        self.assertFalse(self.trader.is_ws_monitoring)

    def test_get_realtime_prices_no_connection(self):
        """Test getting real-time prices when not connected."""
        prices = self.trader.get_realtime_prices()
        self.assertIsInstance(prices, dict)
        self.assertEqual(len(prices), 0)

    def test_get_monitoring_status_initial(self):
        """Test monitoring status before starting."""
        status = self.trader.get_monitoring_status()
        self.assertIsInstance(status, dict)
        self.assertFalse(status['websocket_active'])
        self.assertFalse(status['websocket_connected'])
        self.assertFalse(status['polling_active'])

    def test_stop_realtime_monitoring_not_running(self):
        """Test stopping real-time monitoring when not running."""
        # Should not raise an exception
        self.trader.stop_realtime_monitoring()
        self.assertFalse(self.trader.is_ws_monitoring)


if __name__ == '__main__':
    unittest.main()
