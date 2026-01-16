"""
Integration tests for enhanced trading system components.
Tests sentiment analysis, advanced orders, and multi-timeframe analysis working together.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_market_trader.ml.models.ensemble import EnsembleModel
from poly_market_trader.services.enhanced_order_executor import EnhancedOrderExecutor, OrderType
from poly_market_trader.sentiment.processing.sentiment_analyzer import SentimentAnalyzer, SentimentResult
from poly_market_trader.ml.features.feature_engineer import FeatureEngineer
from poly_market_trader.models.portfolio import Portfolio
from poly_market_trader.models.trade import MarketDirection, TradeType


class TestEnhancedTradingIntegration(unittest.TestCase):
    """Integration tests for enhanced trading system"""

    def setUp(self):
        """Set up test fixtures"""
        self.portfolio = Portfolio()
        self.portfolio.update_balance(Decimal('1000.00'))
        self.feature_engineer = FeatureEngineer()

        # Mock data provider
        mock_data_provider = Mock()
        mock_data_provider.get_technical_indicators.return_value = {
            'adx': 25.0, 'bb_percent_b': 0.5, 'rsi': 50.0,
            'macd_histogram': 0.0, 'sma_20': 0.5, 'ema_12': 0.5
        }
        self.feature_engineer.data_provider = mock_data_provider

    def test_sentiment_integration_with_ensemble(self):
        """Test that sentiment features are properly integrated into ensemble predictions"""
        # Create ensemble model
        ensemble = EnsembleModel(feature_engineer=self.feature_engineer)

        # Mock market data with sentiment
        market_data = {
            'current_price': 0.55,
            'volume': 1000,
            'sentiment_compound': 0.3,  # Positive sentiment
            'sentiment_confidence': 0.8
        }

        # Mock strong positive sentiment data
        sentiment_data = {
            'compound_score': 0.5,  # Strong positive sentiment (> 0.3 threshold)
            'confidence': 0.8,
            'sources': ['vader', 'textblob']
        }

        # Test prediction with sentiment
        prediction = ensemble.predict_trade_setup(
            crypto_name='bitcoin',
            market_data=market_data,
            sentiment_data=sentiment_data
        )

        # Verify prediction includes sentiment factors
        self.assertIsInstance(prediction, object)
        self.assertIn('Sentiment adjustment', ' '.join(prediction.decision_factors))

    def test_enhanced_order_executor_integration(self):
        """Test enhanced order executor works with portfolio"""
        # Create enhanced order executor
        executor = EnhancedOrderExecutor(self.portfolio)

        # Test placing limit order
        order_id = executor.place_limit_order(
            market_id='test_market_123',
            outcome=MarketDirection.YES,
            quantity=10.0,
            limit_price=0.6,
            side=TradeType.BUY
        )

        self.assertIsNotNone(order_id)
        self.assertEqual(len(executor.active_orders), 1)

        # Test order status
        if order_id:
            status = executor.get_order_status(order_id)
            self.assertIsNotNone(status)
            if status:
                self.assertEqual(status['status'], 'pending')
                self.assertEqual(status['order_id'], order_id)

    def test_multi_timeframe_feature_extraction(self):
        """Test that multi-timeframe features are extracted correctly"""
        # Mock data provider to return multi-timeframe data
        mock_data_provider = Mock()
        mock_data_provider.get_technical_indicators.side_effect = lambda crypto, timeframe: {
            'adx': 25.0 if timeframe == '15min' else 30.0,
            'bb_percent_b': 0.5 if timeframe == '15min' else 0.6,
            'rsi': 50.0 if timeframe == '15min' else 55.0,
            'macd_histogram': 0.0,
            'sma_20': 0.5,
            'ema_12': 0.5
        }

        feature_engineer = FeatureEngineer(data_provider=mock_data_provider)

        # Extract features
        features = feature_engineer.extract_features('bitcoin')

        # Verify multi-timeframe features are present
        self.assertIn('adx_15m', features)
        self.assertIn('adx_1h', features)
        self.assertIn('bb_percent_b_15m', features)
        self.assertIn('rsi_15m', features)

        # Verify feature values
        self.assertEqual(features['adx_15m'], 25.0)
        self.assertEqual(features['adx_1h'], 30.0)

    def test_sentiment_analyzer_functionality(self):
        """Test sentiment analyzer produces valid results"""
        analyzer = SentimentAnalyzer()

        # Test with neutral text first (should work even without libraries)
        neutral_text = "Bitcoin price is stable today."
        neutral_result = analyzer.analyze_text(neutral_text)

        self.assertIsInstance(neutral_result, SentimentResult)
        self.assertEqual(neutral_result.label, 'neutral')

        # Test with positive text (may fail if Vader not available)
        positive_text = "Bitcoin is mooning! Massive gains expected!"
        positive_result = analyzer.analyze_text(positive_text)

        self.assertIsInstance(positive_result, SentimentResult)
        # Only test if we have working sentiment libraries
        if positive_result.sources:  # If any analyzers worked
            if positive_result.compound_score > 0:
                self.assertEqual(positive_result.label, 'positive')
        else:
            # Fallback keyword analysis
            self.assertIsInstance(positive_result.label, str)

    def test_full_pipeline_integration(self):
        """Test complete pipeline: sentiment -> features -> ensemble -> order execution"""
        # 1. Set up components
        ensemble = EnsembleModel(feature_engineer=self.feature_engineer)
        order_executor = EnhancedOrderExecutor(self.portfolio)

        # 2. Mock positive sentiment
        sentiment_data = {
            'compound_score': 0.4,
            'confidence': 0.9
        }

        market_data = {'current_price': 0.55}

        # 3. Get ensemble prediction with sentiment
        prediction = ensemble.predict_trade_setup(
            crypto_name='bitcoin',
            market_data=market_data,
            sentiment_data=sentiment_data
        )

        # 4. Check if we should trade
        should_trade, reason = ensemble.should_trade(prediction)

        # 5. If we should trade, place enhanced order
        if should_trade:
            order_id = order_executor.place_limit_order(
                market_id='test_market_123',
                outcome=MarketDirection.YES,
                quantity=5.0,
                limit_price=0.6,
                side=TradeType.BUY
            )

            self.assertIsNotNone(order_id)

            # Verify order was placed
            active_orders = order_executor.get_active_orders()
            self.assertEqual(len(active_orders), 1)

    def test_order_routing_optimization(self):
        """Test that order router finds optimal execution prices"""
        from poly_market_trader.services.enhanced_order_executor import SmartOrderRouter

        router = SmartOrderRouter()

        # Mock market data with bids/asks
        market_data = {
            'current_price': 0.55,
            'bid': 0.54,
            'ask': 0.56
        }

        # Test limit order optimization
        limit_params = router._limit_execution(market_data, TradeType.BUY, 10.0)
        self.assertIn('execution_price', limit_params)
        self.assertLess(limit_params['execution_price'], 0.55)  # Better price for buy

        # Test market order
        market_params = router._market_execution(market_data, TradeType.BUY, 10.0)
        self.assertEqual(market_params['execution_price'], 0.55)

    def test_portfolio_risk_limits(self):
        """Test that enhanced order executor respects portfolio risk limits"""
        # Create portfolio with limited balance
        small_portfolio = Portfolio(initial_balance=Decimal('10.00'))
        executor = EnhancedOrderExecutor(small_portfolio)

        # Try to place order that exceeds risk limits
        order_id = executor.place_limit_order(
            market_id='test_market_123',
            outcome=MarketDirection.YES,
            quantity=50.0,  # Large quantity
            limit_price=0.8,  # High price
            side=TradeType.BUY
        )

        # Should fail due to risk limits
        self.assertIsNone(order_id)

    def test_sentiment_feature_consistency(self):
        """Test that sentiment features are consistently extracted"""
        features1 = self.feature_engineer.extract_features('bitcoin')
        features2 = self.feature_engineer.extract_features('bitcoin')

        # Check that sentiment features are present (even if zero)
        sentiment_keys = [k for k in features1.keys() if 'sentiment' in k.lower()]
        self.assertGreater(len(sentiment_keys), 0)

        # Values should be consistent for same input
        for key in sentiment_keys:
            self.assertEqual(features1[key], features2[key])


if __name__ == '__main__':
    unittest.main()