"""
Ensemble model combining rule-based and ML predictions.
Provides unified interface for enhanced trading decisions.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_market_trader.ml.models.win_probability import WinProbabilityModel
from poly_market_trader.ml.features.feature_engineer import FeatureEngineer


@dataclass
class EnsemblePrediction:
    """Combined prediction from ensemble model"""
    final_win_probability: float
    final_confidence: float
    rule_based_score: float
    ml_score: float
    ensemble_method: str
    feature_importance: Dict[str, float]
    decision_factors: List[str]
    prediction_timestamp: datetime


class EnsembleModel:
    """
    Ensemble model that combines rule-based trading logic with ML predictions.
    Provides sophisticated decision-making for trade entry and position sizing.
    """

    def __init__(self,
                 win_probability_model: Optional[WinProbabilityModel] = None,
                 feature_engineer: Optional[FeatureEngineer] = None,
                 rule_weight: float = 0.4,
                 ml_weight: float = 0.6):
        """
        Initialize ensemble model.

        Args:
            win_probability_model: Trained ML win probability model
            feature_engineer: Feature engineering instance
            rule_weight: Weight for rule-based predictions (0-1)
            ml_weight: Weight for ML predictions (0-1)
        """
        self.win_probability_model = win_probability_model or WinProbabilityModel()
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.rule_weight = rule_weight
        self.ml_weight = ml_weight

        # Decision thresholds
        self.min_confidence_threshold = 0.6  # Minimum confidence to trade
        self.high_confidence_threshold = 0.75  # High confidence for larger positions

    def predict_trade_setup(self,
                            crypto_name: str,
                            market_data: Optional[Dict[str, Any]] = None,
                            rule_based_analysis: Optional[Dict[str, Any]] = None,
                            sentiment_data: Optional[Dict[str, Any]] = None) -> EnsemblePrediction:
        """
        Generate ensemble prediction for a potential trade setup.

        Args:
            crypto_name: Cryptocurrency name
            market_data: Current market data from trading context
            rule_based_analysis: Results from rule-based strategy analysis
            sentiment_data: Optional sentiment data to override automatic extraction

        Returns:
            Ensemble prediction combining all available signals
        """

        # Get ML prediction (sentiment features are automatically extracted)
        ml_prediction = self.win_probability_model.predict(crypto_name, market_data)

        # Get rule-based prediction
        rule_prediction = self._calculate_rule_based_score(crypto_name, market_data, rule_based_analysis, sentiment_data)

        # Combine predictions using ensemble method
        ensemble_result = self._combine_predictions(ml_prediction, rule_prediction)

        return ensemble_result

    def _calculate_rule_based_score(self,
                                   crypto_name: str,
                                   market_data: Optional[Dict[str, Any]] = None,
                                   rule_based_analysis: Optional[Dict[str, Any]] = None,
                                   sentiment_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate rule-based prediction score using current strategy logic.
        This mirrors the enhanced filtering logic from the trading system.
        """

        # Extract features for rule-based analysis
        features = self.feature_engineer.extract_features(crypto_name, market_data)

        # Rule-based decision logic (mirroring MarketMonitor._analyze_and_bet)
        adx = features.get('adx_15m', 25.0)
        bb_percent = features.get('bb_percent_b_15m', 0.5)
        rsi = features.get('rsi_15m', 50.0)

        # Initialize scoring
        rule_score = 0.5  # Neutral starting point
        confidence = 0.0
        factors = []

        # Trend filter
        is_strong_trend = adx > 25.0
        if is_strong_trend:
            rule_score = 0.3  # Low probability for mean reversion in strong trends
            confidence = 0.8
            factors.append("Strong trend detected (ADX > 25)")
        else:
            factors.append("Weak trend suitable for mean reversion")

        # Bollinger Band + RSI extreme conditions
        is_extreme_bb = bb_percent < 0.15 or bb_percent > 0.85
        is_extreme_rsi = rsi < 35 or rsi > 65

        if is_extreme_bb and is_extreme_rsi:
            confidence = 0.8
            factors.append("Extreme BB + RSI conditions")

            # Determine direction and adjust score
            if bb_percent < 0.15 and rsi < 35:
                rule_score = 0.75  # Strong bullish signal
                factors.append("Oversold conditions - expect bounce")
            elif bb_percent > 0.85 and rsi > 65:
                rule_score = 0.25  # Strong bearish signal (win if we bet NO)
                factors.append("Overbought conditions - expect pullback")
            else:
                rule_score = 0.55
                confidence = 0.6
                factors.append("Mixed extreme signals")
        elif is_extreme_bb or is_extreme_rsi:
            confidence = 0.6
            factors.append("Single extreme indicator")
            rule_score = 0.6 if bb_percent < 0.15 or rsi < 35 else 0.4
        else:
            confidence = 0.4
            factors.append("No extreme conditions")
            rule_score = 0.5

        # Incorporate additional rule-based analysis if provided
        if rule_based_analysis:
            llm_confidence = rule_based_analysis.get('llm_confidence', 0.5)
            rule_score = (rule_score * 0.7) + (llm_confidence * 0.3)  # Blend with LLM
            factors.append(f"LLM confidence: {llm_confidence:.2f}")

        # Incorporate sentiment data if provided
        if sentiment_data:
            sentiment_score = sentiment_data.get('compound_score', 0.0)
            sentiment_confidence = sentiment_data.get('confidence', 0.5)

            # Adjust rule score based on sentiment (strong sentiment can amplify signals)
            if abs(sentiment_score) > 0.3:  # Strong sentiment threshold
                sentiment_adjustment = sentiment_score * 0.1 * sentiment_confidence  # 10% max adjustment
                rule_score += sentiment_adjustment
                rule_score = max(0.1, min(0.9, rule_score))  # Keep in reasonable bounds

                direction = "positive" if sentiment_adjustment > 0 else "negative"
                factors.append(f"Sentiment adjustment: {direction} ({sentiment_adjustment:.2f})")

        return {
            'win_probability': rule_score,
            'confidence': confidence,
            'factors': factors,
            'features': features
        }

    def _combine_predictions(self,
                           ml_prediction: Any,
                           rule_prediction: Dict[str, Any]) -> EnsemblePrediction:
        """
        Combine ML and rule-based predictions using ensemble method.
        """

        # Extract components
        ml_prob = getattr(ml_prediction, 'win_probability', 0.5)
        ml_conf = getattr(ml_prediction, 'confidence_score', 0.5)

        rule_prob = rule_prediction.get('win_probability', 0.5)
        rule_conf = rule_prediction.get('confidence', 0.5)

        # Weighted ensemble
        # Use confidence scores to weight the predictions
        total_weight = self.rule_weight * rule_conf + self.ml_weight * ml_conf

        if total_weight > 0:
            final_probability = (
                (rule_prob * self.rule_weight * rule_conf) +
                (ml_prob * self.ml_weight * ml_conf)
            ) / total_weight
        else:
            final_probability = (rule_prob + ml_prob) / 2

        # Ensemble confidence based on agreement and individual confidences
        agreement_bonus = 1.0 if abs(ml_prob - rule_prob) < 0.2 else 0.8
        final_confidence = min(0.95, (rule_conf + ml_conf) / 2 * agreement_bonus)

        # Determine ensemble method description
        if abs(ml_prob - rule_prob) < 0.1:
            method = "High Agreement"
        elif abs(ml_prob - rule_prob) < 0.3:
            method = "Moderate Agreement"
        else:
            method = "Divergent Signals"

        # Combine decision factors
        rule_factors = rule_prediction.get('factors', [])
        ml_factors = ["ML Prediction"]
        if hasattr(ml_prediction, 'feature_contributions'):
            top_features = sorted(ml_prediction.feature_contributions.items(),
                                key=lambda x: abs(x[1]), reverse=True)[:3]
            ml_factors.extend([f"{k}: {v:.3f}" for k, v in top_features])

        decision_factors = rule_factors + ml_factors

        # Feature importance (combine from both sources)
        feature_importance = {}
        if hasattr(ml_prediction, 'feature_contributions'):
            feature_importance.update(ml_prediction.feature_contributions)

        # Add rule-based feature importance
        rule_features = rule_prediction.get('features', {})
        for key in ['adx_15m', 'bb_percent_b_15m', 'rsi_15m']:
            if key in rule_features:
                feature_importance[key] = feature_importance.get(key, 0) + 0.1

        return EnsemblePrediction(
            final_win_probability=final_probability,
            final_confidence=final_confidence,
            rule_based_score=rule_prob,
            ml_score=ml_prob,
            ensemble_method=method,
            feature_importance=feature_importance,
            decision_factors=decision_factors,
            prediction_timestamp=datetime.now()
        )

    def should_trade(self, ensemble_prediction: EnsemblePrediction) -> Tuple[bool, str]:
        """
        Determine if we should execute a trade based on ensemble prediction.

        Args:
            ensemble_prediction: Result from predict_trade_setup

        Returns:
            (should_trade, reason)
        """

        # Minimum confidence threshold
        if ensemble_prediction.final_confidence < self.min_confidence_threshold:
            return False, f"Low confidence ({ensemble_prediction.final_confidence:.2f} < {self.min_confidence_threshold})"

        # Check for extreme probabilities (too close to 0.5 might indicate uncertainty)
        prob = ensemble_prediction.final_win_probability
        if 0.45 < prob < 0.55:
            return False, f"Probability too close to 50% ({prob:.2f}) - high uncertainty"

        return True, f"Strong signal: {prob:.2f} probability, {ensemble_prediction.final_confidence:.2f} confidence"

    def calculate_position_size(self,
                              ensemble_prediction: EnsemblePrediction,
                              base_portfolio_value: float,
                              max_position_size: float = 0.05) -> Tuple[float, str]:
        """
        Calculate optimal position size based on ensemble prediction.

        Args:
            ensemble_prediction: Ensemble prediction result
            base_portfolio_value: Current portfolio value
            max_position_size: Maximum position size as fraction of portfolio

        Returns:
            (position_size, reasoning)
        """

        confidence = ensemble_prediction.final_confidence
        probability = ensemble_prediction.final_win_probability

        # Base position size from confidence
        if confidence > self.high_confidence_threshold:
            confidence_multiplier = 1.5  # 50% larger position for high confidence
            size_reason = "High confidence signal"
        elif confidence > self.min_confidence_threshold:
            confidence_multiplier = 1.0  # Standard size
            size_reason = "Standard confidence signal"
        else:
            confidence_multiplier = 0.5  # Smaller position for lower confidence
            size_reason = "Lower confidence - reduced size"

        # Probability adjustment (prefer trades with clear edge)
        edge = abs(probability - 0.5) * 2  # Convert to 0-1 scale
        probability_multiplier = 0.8 + (edge * 0.4)  # 0.8 to 1.2 range

        # Calculate final position size
        base_size = base_portfolio_value * max_position_size
        adjusted_size = base_size * confidence_multiplier * probability_multiplier
        final_size = min(adjusted_size, base_portfolio_value * max_position_size)

        detailed_reason = f"{size_reason}, edge: {edge:.2f}, multipliers: {confidence_multiplier:.1f}x conf, {probability_multiplier:.1f}x prob"

        return final_size, detailed_reason

    def get_model_status(self) -> Dict[str, Any]:
        """Get current status of ensemble model components"""
        return {
            'ml_model_trained': self.win_probability_model.is_trained,
            'rule_based_active': True,
            'ensemble_weights': {
                'rule_based': self.rule_weight,
                'ml': self.ml_weight
            },
            'confidence_thresholds': {
                'minimum': self.min_confidence_threshold,
                'high': self.high_confidence_threshold
            }
        }