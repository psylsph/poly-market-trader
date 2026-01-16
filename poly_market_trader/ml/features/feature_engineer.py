"""
Feature engineering pipeline for ML models.
Extracts and transforms features from market data for predictive modeling.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_market_trader.api.chainlink_data_provider import ChainlinkDataProvider
from poly_market_trader.services.market_monitor import MarketMonitor
from poly_market_trader.sentiment.sources.news_api import NewsAPIClient, get_mock_news_data
from poly_market_trader.sentiment.processing.sentiment_analyzer import SentimentAnalyzer


class FeatureEngineer:
    """
    Comprehensive feature engineering for ML-based trading strategy.
    Extracts technical, market context, and historical performance features.
    """

    def __init__(self, data_provider: Optional[ChainlinkDataProvider] = None):
        """
        Initialize feature engineer.

        Args:
            data_provider: Chainlink data provider for real-time data access
        """
        self.data_provider = data_provider or ChainlinkDataProvider()
        self.feature_cache = {}  # Cache for expensive computations

    def extract_features(self, crypto_name: str, market_data: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Extract comprehensive feature set for ML prediction.

        Args:
            crypto_name: Cryptocurrency name (bitcoin, ethereum, etc.)
            market_data: Optional market data dict from trading context

        Returns:
            Dictionary of feature names and values
        """
        features = {}

        try:
            # Get technical indicators from multiple timeframes
            tech_15m = self.data_provider.get_technical_indicators(crypto_name, timeframe='15min')
            tech_1h = self.data_provider.get_technical_indicators(crypto_name, timeframe='1hour')

            # Get additional timeframes for comprehensive analysis
            try:
                tech_4h = self.data_provider.get_technical_indicators(crypto_name, timeframe='4hour')
                tech_1d = self.data_provider.get_technical_indicators(crypto_name, timeframe='1day')
            except Exception as e:
                print(f"Warning: Could not fetch higher timeframe data: {e}")
                tech_4h = None
                tech_1d = None

            # Technical Features with multi-timeframe analysis
            features.update(self._extract_technical_features(tech_15m, tech_1h, tech_4h, tech_1d))

            # Market Context Features
            features.update(self._extract_market_context_features(crypto_name, market_data))

            # Historical Performance Features
            features.update(self._extract_historical_features(crypto_name))

            # Time-based Features
            features.update(self._extract_time_features())

            # Price Action Features
            features.update(self._extract_price_action_features(crypto_name))

            # Sentiment Features
            features.update(self._extract_sentiment_features(crypto_name))

            return features

        except Exception as e:
            print(f"Error extracting features for {crypto_name}: {e}")
            return self._get_default_features()

    def _extract_technical_features(self, tech_15m: Dict[str, float], tech_1h: Dict[str, float],
                                   tech_4h: Optional[Dict[str, float]] = None,
                                   tech_1d: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """Extract technical indicator features from 15m and 1h data"""
        features = {}

        # 15-minute timeframe features
        features['adx_15m'] = tech_15m.get('adx', 25.0)
        features['bb_percent_b_15m'] = tech_15m.get('bb_percent_b', 0.5)
        features['bb_upper_15m'] = tech_15m.get('bb_upper', 0.0)
        features['bb_lower_15m'] = tech_15m.get('bb_lower', 0.0)
        features['rsi_15m'] = tech_15m.get('rsi', 50.0)
        features['macd_line_15m'] = tech_15m.get('macd_line', 0.0)
        features['macd_signal_15m'] = tech_15m.get('signal_line', 0.0)
        features['macd_histogram_15m'] = tech_15m.get('macd_histogram', 0.0)
        features['sma_9_15m'] = tech_15m.get('sma_9', 0.0)
        features['sma_20_15m'] = tech_15m.get('sma_20', 0.0)
        features['sma_50_15m'] = tech_15m.get('sma_50', 0.0)
        features['volatility_15m'] = tech_15m.get('volatility', 0.0)

        # 1-hour timeframe features
        features['adx_1h'] = tech_1h.get('adx', 25.0) if tech_1h else 25.0
        features['bb_percent_b_1h'] = tech_1h.get('bb_percent_b', 0.5) if tech_1h else 0.5
        features['rsi_1h'] = tech_1h.get('rsi', 50.0) if tech_1h else 50.0
        features['macd_histogram_1h'] = tech_1h.get('macd_histogram', 0.0) if tech_1h else 0.0

        # 4-hour timeframe features
        features['adx_4h'] = tech_4h.get('adx', 25.0) if tech_4h else 25.0
        features['bb_percent_b_4h'] = tech_4h.get('bb_percent_b', 0.5) if tech_4h else 0.5
        features['rsi_4h'] = tech_4h.get('rsi', 50.0) if tech_4h else 50.0

        # Daily timeframe features
        features['adx_1d'] = tech_1d.get('adx', 25.0) if tech_1d else 25.0
        features['bb_percent_b_1d'] = tech_1d.get('bb_percent_b', 0.5) if tech_1d else 0.5
        features['rsi_1d'] = tech_1d.get('rsi', 50.0) if tech_1d else 50.0

        # Multi-timeframe consensus and relationships
        features['adx_trend_15m'] = 1.0 if features['adx_15m'] > 25 else 0.0
        features['adx_trend_1h'] = 1.0 if features['adx_1h'] > 25 else 0.0
        features['adx_trend_4h'] = 1.0 if features['adx_4h'] > 25 else 0.0
        features['adx_trend_1d'] = 1.0 if features['adx_1d'] > 25 else 0.0

        # Enhanced consensus scoring across multiple timeframes
        features['adx_consensus_2tf'] = 1.0 if features['adx_trend_15m'] == features['adx_trend_1h'] else 0.0
        features['adx_consensus_3tf'] = 1.0 if (features['adx_trend_15m'] == features['adx_trend_1h'] == features['adx_trend_4h']) else 0.0
        features['adx_consensus_4tf'] = 1.0 if (features['adx_trend_15m'] == features['adx_trend_1h'] == features['adx_trend_4h'] == features['adx_trend_1d']) else 0.0

        # RSI consensus across timeframes
        rsi_extreme_15m = 1.0 if (features['rsi_15m'] < 35 or features['rsi_15m'] > 65) else 0.0
        rsi_extreme_1h = 1.0 if (features['rsi_1h'] < 35 or features['rsi_1h'] > 65) else 0.0
        rsi_extreme_4h = 1.0 if (features['rsi_4h'] < 35 or features['rsi_4h'] > 65) else 0.0

        features['rsi_consensus_2tf'] = 1.0 if rsi_extreme_15m == rsi_extreme_1h else 0.0
        features['rsi_consensus_3tf'] = 1.0 if (rsi_extreme_15m == rsi_extreme_1h == rsi_extreme_4h) else 0.0

        # Bollinger Band consensus
        bb_extreme_15m = 1.0 if (features['bb_percent_b_15m'] < 0.15 or features['bb_percent_b_15m'] > 0.85) else 0.0
        bb_extreme_1h = 1.0 if (features['bb_percent_b_1h'] < 0.15 or features['bb_percent_b_1h'] > 0.85) else 0.0
        bb_extreme_4h = 1.0 if (features['bb_percent_b_4h'] < 0.15 or features['bb_percent_b_4h'] > 0.85) else 0.0

        features['bb_consensus_2tf'] = 1.0 if bb_extreme_15m == bb_extreme_1h else 0.0
        features['bb_consensus_3tf'] = 1.0 if (bb_extreme_15m == bb_extreme_1h == bb_extreme_4h) else 0.0

        # Overall timeframe consensus score (weighted average)
        consensus_weights = {
            'adx_consensus_4tf': 0.3,  # Most important for trend
            'adx_consensus_3tf': 0.2,
            'rsi_consensus_3tf': 0.2,  # Important for momentum
            'bb_consensus_3tf': 0.15,  # Important for volatility
            'adx_consensus_2tf': 0.1,
            'rsi_consensus_2tf': 0.03,
            'bb_consensus_2tf': 0.02
        }

        features['timeframe_consensus_score'] = sum(
            features[metric] * weight for metric, weight in consensus_weights.items()
        )

        # Multi-timeframe strength indicators
        features['trend_strength_multitf'] = (
            (features['adx_15m'] * 0.4) +
            (features['adx_1h'] * 0.35) +
            (features['adx_4h'] * 0.2) +
            (features['adx_1d'] * 0.05)
        ) / 100.0  # Normalize to 0-1 range

        features['momentum_strength_multitf'] = (
            (abs(features['rsi_15m'] - 50) * 0.4) +
            (abs(features['rsi_1h'] - 50) * 0.35) +
            (abs(features['rsi_4h'] - 50) * 0.2) +
            (abs(features['rsi_1d'] - 50) * 0.05)
        ) / 50.0  # Normalize to 0-1 range

        # Legacy agreement metric for backward compatibility
        features['adx_agreement'] = features['adx_consensus_2tf']

        # Bollinger Band position analysis
        bb_pos = features['bb_percent_b_15m']
        features['bb_extreme_oversold'] = 1.0 if bb_pos < 0.15 else 0.0
        features['bb_extreme_overbought'] = 1.0 if bb_pos > 0.85 else 0.0
        features['bb_neutral'] = 1.0 if 0.3 <= bb_pos <= 0.7 else 0.0

        # RSI extreme conditions
        rsi = features['rsi_15m']
        features['rsi_extreme_oversold'] = 1.0 if rsi < 35 else 0.0
        features['rsi_extreme_overbought'] = 1.0 if rsi > 65 else 0.0
        features['rsi_neutral'] = 1.0 if 40 <= rsi <= 60 else 0.0

        # MACD signals
        macd_hist = features['macd_histogram_15m']
        features['macd_bullish'] = 1.0 if macd_hist > 0 else 0.0
        features['macd_bearish'] = 1.0 if macd_hist < 0 else 0.0

        # Moving average relationships
        sma_9 = features['sma_9_15m']
        sma_20 = features['sma_20_15m']
        sma_50 = features['sma_50_15m']

        if sma_20 > 0:
            features['sma_alignment_bullish'] = 1.0 if sma_9 > sma_20 > sma_50 else 0.0
            features['sma_alignment_bearish'] = 1.0 if sma_9 < sma_20 < sma_50 else 0.0
        else:
            features['sma_alignment_bullish'] = 0.0
            features['sma_alignment_bearish'] = 0.0

        return features

    def _extract_market_context_features(self, crypto_name: str, market_data: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """Extract market context and external factor features"""
        features = {}

        # Cryptocurrency-specific characteristics
        crypto_mapping = {
            'bitcoin': 0.0,
            'btc': 0.0,
            'ethereum': 1.0,
            'eth': 1.0,
            'solana': 2.0,
            'sol': 2.0,
            'ripple': 3.0,
            'xrp': 3.0
        }
        features['crypto_type'] = crypto_mapping.get(crypto_name.lower(), 4.0)

        # Market data features (if available)
        if market_data:
            # Market liquidity proxy (YES + NO should be close to 1.0)
            yes_price = market_data.get('yes_price', 0.5)
            no_price = market_data.get('no_price', 0.5)
            market_sum = yes_price + no_price
            features['market_efficiency'] = 1.0 - abs(market_sum - 1.0)  # Closer to 1.0 = more efficient

            # Arbitrage opportunity indicator
            features['arbitrage_opportunity'] = 1.0 if market_sum < 0.99 else 0.0

            # Volume and liquidity indicators (placeholder for now)
            features['market_volume_proxy'] = market_data.get('volume', 1000000) / 1000000  # Normalized

        else:
            features['market_efficiency'] = 0.5
            features['arbitrage_opportunity'] = 0.0
            features['market_volume_proxy'] = 0.5

        return features

    def _extract_historical_features(self, crypto_name: str) -> Dict[str, float]:
        """Extract historical performance and momentum features"""
        features = {}

        # Placeholder for historical performance features
        # In a real implementation, this would analyze past trades for this crypto
        features['recent_win_rate_10'] = 0.5  # Last 10 trades win rate
        features['recent_win_rate_50'] = 0.5  # Last 50 trades win rate
        features['avg_profit_last_10'] = 0.0  # Average profit last 10 trades
        features['consecutive_wins'] = 0.0    # Current win streak
        features['consecutive_losses'] = 0.0  # Current loss streak

        # Momentum features (simplified)
        features['momentum_1d'] = 0.0  # 1-day price momentum
        features['momentum_1w'] = 0.0  # 1-week price momentum

        return features

    def _extract_time_features(self) -> Dict[str, float]:
        """Extract time-based features"""
        features = {}

        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Hour of day (cyclic encoding)
        features['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        features['hour_cos'] = np.cos(2 * np.pi * hour / 24)

        # Day of week (cyclic encoding)
        features['weekday_sin'] = np.sin(2 * np.pi * weekday / 7)
        features['weekday_cos'] = np.cos(2 * np.pi * weekday / 7)

        # Market session indicators
        features['is_market_hours'] = 1.0 if 9 <= hour <= 16 else 0.0  # Rough market hours
        features['is_asian_session'] = 1.0 if 0 <= hour <= 8 else 0.0
        features['is_european_session'] = 1.0 if 8 <= hour <= 16 else 0.0
        features['is_us_session'] = 1.0 if 14 <= hour <= 21 else 0.0

        return features

    def _extract_price_action_features(self, crypto_name: str) -> Dict[str, float]:
        """Extract price action and pattern recognition features"""
        features = {}

        try:
            # Get recent price data
            current_price = self.data_provider.get_current_price(crypto_name)
            if current_price:
                # Get short-term trend
                trend_15m = self.data_provider.get_recent_trend_15min(crypto_name, lookback_minutes=30)
                volatility_15m = self.data_provider.get_volatility_15min(crypto_name, lookback_minutes=60)

                # Trend encoding
                trend_mapping = {'bullish': 1.0, 'bearish': -1.0, 'sideways': 0.0}
                features['trend_15m'] = trend_mapping.get(trend_15m, 0.0)

                # Volatility features
                features['volatility_15m'] = volatility_15m or 0.0
                features['volatility_regime'] = 1.0 if (volatility_15m or 0) > 0.02 else 0.0  # High vol threshold

            else:
                features['trend_15m'] = 0.0
                features['volatility_15m'] = 0.0
                features['volatility_regime'] = 0.0

        except Exception as e:
            print(f"Error extracting price action features: {e}")
            features['trend_15m'] = 0.0
            features['volatility_15m'] = 0.0
            features['volatility_regime'] = 0.0

        return features

    def _extract_sentiment_features(self, crypto_name: str) -> Dict[str, float]:
        """Extract sentiment-based features from news and social media"""

        features = {}

        try:
            # Initialize sentiment analyzer
            sentiment_analyzer = SentimentAnalyzer()

            # Try to get real news data
            news_client = NewsAPIClient()

            if news_client.api_key:
                # Fetch real news
                articles = news_client.fetch_crypto_news(hours_back=24, limit=20)
            else:
                # Use mock data for testing
                articles = get_mock_news_data()

            # Analyze sentiment
            if articles:
                analyzed_articles = sentiment_analyzer.analyze_articles(articles)

                # Filter articles relevant to this crypto
                relevant_articles = []
                for article in analyzed_articles:
                    if crypto_name.lower() in [mention.lower() for mention in article.crypto_mentions]:
                        relevant_articles.append(article)

                if relevant_articles:
                    # Calculate sentiment metrics
                    sentiments = [article.sentiment_score for article in relevant_articles]
                    sentiment_volatility = np.std(sentiments) if len(sentiments) > 1 else 0

                    # Sentiment features
                    features['news_sentiment_avg'] = np.mean(sentiments)
                    features['news_sentiment_std'] = sentiment_volatility
                    features['news_sentiment_max'] = max(sentiments) if sentiments else 0
                    features['news_sentiment_min'] = min(sentiments) if sentiments else 0

                    # Sentiment trend (recent vs older articles)
                    mid_point = len(relevant_articles) // 2
                    if mid_point > 0:
                        recent_sentiment = np.mean([a.sentiment_score for a in relevant_articles[:mid_point]])
                        older_sentiment = np.mean([a.sentiment_score for a in relevant_articles[mid_point:]])
                        features['news_sentiment_trend'] = recent_sentiment - older_sentiment
                    else:
                        features['news_sentiment_trend'] = 0

                    # Positive/negative article counts
                    positive_count = sum(1 for a in relevant_articles if a.sentiment_label == 'positive')
                    negative_count = sum(1 for a in relevant_articles if a.sentiment_label == 'negative')
                    neutral_count = len(relevant_articles) - positive_count - negative_count

                    features['news_positive_ratio'] = positive_count / len(relevant_articles)
                    features['news_negative_ratio'] = negative_count / len(relevant_articles)
                    features['news_neutral_ratio'] = neutral_count / len(relevant_articles)

                    # Article volume and recency
                    features['news_article_count'] = len(relevant_articles)
                    features['news_avg_relevance'] = np.mean([a.relevance_score for a in relevant_articles])

                else:
                    # No relevant articles
                    features.update({
                        'news_sentiment_avg': 0.0,
                        'news_sentiment_std': 0.0,
                        'news_sentiment_max': 0.0,
                        'news_sentiment_min': 0.0,
                        'news_sentiment_trend': 0.0,
                        'news_positive_ratio': 0.0,
                        'news_negative_ratio': 0.0,
                        'news_neutral_ratio': 0.0,
                        'news_article_count': 0.0,
                        'news_avg_relevance': 0.0
                    })
            else:
                # No articles available
                features.update({
                    'news_sentiment_avg': 0.0,
                    'news_sentiment_std': 0.0,
                    'news_sentiment_max': 0.0,
                    'news_sentiment_min': 0.0,
                    'news_sentiment_trend': 0.0,
                    'news_positive_ratio': 0.0,
                    'news_negative_ratio': 0.0,
                    'news_neutral_ratio': 0.0,
                    'news_article_count': 0.0,
                    'news_avg_relevance': 0.0
                })

        except Exception as e:
            print(f"Error extracting sentiment features: {e}")
            # Fallback values
            features.update({
                'news_sentiment_avg': 0.0,
                'news_sentiment_std': 0.0,
                'news_sentiment_max': 0.0,
                'news_sentiment_min': 0.0,
                'news_sentiment_trend': 0.0,
                'news_positive_ratio': 0.0,
                'news_negative_ratio': 0.0,
                'news_neutral_ratio': 0.0,
                'news_article_count': 0.0,
                'news_avg_relevance': 0.0
            })

        return features

    def _get_default_features(self) -> Dict[str, float]:
        """Return default feature values when extraction fails"""
        return {
            'adx_15m': 25.0,
            'bb_percent_b_15m': 0.5,
            'rsi_15m': 50.0,
            'macd_histogram_15m': 0.0,
            'volatility_15m': 0.0,
            'adx_trend_15m': 0.0,
            'bb_extreme_oversold': 0.0,
            'bb_extreme_overbought': 0.0,
            'rsi_extreme_oversold': 0.0,
            'rsi_extreme_overbought': 0.0,
            'crypto_type': 4.0,
            'market_efficiency': 0.5,
            'arbitrage_opportunity': 0.0,
            'hour_sin': 0.0,
            'hour_cos': 1.0,
            'trend_15m': 0.0,
            'volatility_regime': 0.0,
            'news_sentiment_avg': 0.0,
            'news_sentiment_std': 0.0,
            'news_sentiment_max': 0.0,
            'news_sentiment_min': 0.0,
            'news_sentiment_trend': 0.0,
            'news_positive_ratio': 0.0,
            'news_negative_ratio': 0.0,
            'news_neutral_ratio': 0.0,
            'news_article_count': 0.0,
            'news_avg_relevance': 0.0,
            # Multi-timeframe features
            'adx_1h': 25.0,
            'bb_percent_b_1h': 0.5,
            'rsi_1h': 50.0,
            'macd_histogram_1h': 0.0,
            'adx_4h': 25.0,
            'bb_percent_b_4h': 0.5,
            'rsi_4h': 50.0,
            'adx_1d': 25.0,
            'bb_percent_b_1d': 0.5,
            'rsi_1d': 50.0,
            'adx_trend_1h': 0.0,
            'adx_trend_4h': 0.0,
            'adx_trend_1d': 0.0,
            'adx_consensus_2tf': 0.0,
            'adx_consensus_3tf': 0.0,
            'adx_consensus_4tf': 0.0,
            'rsi_consensus_2tf': 0.0,
            'rsi_consensus_3tf': 0.0,
            'bb_consensus_2tf': 0.0,
            'bb_consensus_3tf': 0.0,
            'timeframe_consensus_score': 0.0,
            'trend_strength_multitf': 0.0,
            'momentum_strength_multitf': 0.0
        }

    def get_feature_names(self) -> List[str]:
        """Get list of all feature names in consistent order"""
        # Extract from a dummy call to ensure consistency
        dummy_features = self._get_default_features()
        return sorted(dummy_features.keys())

    def prepare_feature_matrix(self, feature_dicts: List[Dict[str, float]]) -> Tuple[np.ndarray, List[str]]:
        """
        Convert list of feature dictionaries to numpy matrix for ML.

        Args:
            feature_dicts: List of feature dictionaries

        Returns:
            Feature matrix and feature names
        """
        if not feature_dicts:
            return np.array([]), []

        feature_names = self.get_feature_names()
        feature_matrix = []

        for feature_dict in feature_dicts:
            row = []
            for name in feature_names:
                row.append(feature_dict.get(name, 0.0))
            feature_matrix.append(row)

        return np.array(feature_matrix), feature_names