"""
Real-time prediction interface for ML-enhanced trading.
Provides live predictions integrated with existing trading logic.
"""

import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Union
from datetime import datetime, timedelta
import threading
import time
import json
import os
import sys

# Optional imports
try:
    import joblib
    HAS_JOBLIB = True
except ImportError:
    HAS_JOBLIB = False

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poly_market_trader.ml.models.ensemble import EnsembleModel
from poly_market_trader.ml.features.feature_engineer import FeatureEngineer


class RealTimePredictor:
    """
    Real-time prediction service that integrates ML models with live trading.
    Provides thread-safe predictions with caching and monitoring.
    """

    def __init__(self,
                 ensemble_model: Optional[EnsembleModel] = None,
                 update_interval: int = 60,  # Update predictions every 60 seconds
                 cache_ttl: int = 30):       # Cache predictions for 30 seconds
        """
        Initialize real-time predictor.

        Args:
            ensemble_model: Trained ensemble model
            update_interval: Seconds between background updates
            cache_ttl: Seconds to cache predictions
        """
        self.ensemble_model = ensemble_model or EnsembleModel()
        self.update_interval = update_interval
        self.cache_ttl = cache_ttl

        # Prediction cache
        self.prediction_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}

        # Background update thread
        self.update_thread = None
        self.running = False

        # Performance monitoring
        self.prediction_count = 0
        self.cache_hit_rate = 0.0
        self.avg_prediction_time = 0.0

    def start(self):
        """Start the real-time prediction service"""
        if self.running:
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._background_update_loop, daemon=True)
        self.update_thread.start()
        print("Real-time predictor started")

    def stop(self):
        """Stop the real-time prediction service"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        print("Real-time predictor stopped")

    def get_prediction(self,
                      crypto_name: str,
                      market_data: Optional[Dict[str, Any]] = None,
                      rule_based_analysis: Optional[Dict[str, Any]] = None,
                      use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get real-time prediction for a trade setup.

        Args:
            crypto_name: Cryptocurrency name
            market_data: Current market data
            rule_based_analysis: Rule-based analysis results
            use_cache: Whether to use cached predictions

        Returns:
            Prediction result dictionary or None if error
        """

        cache_key = f"{crypto_name}_{hash(str(market_data) + str(rule_based_analysis))}"

        # Check cache first
        if use_cache and self._is_cache_valid(cache_key):
            self.cache_hit_rate = (self.cache_hit_rate * 0.9) + 0.1  # Exponential moving average
            return self.prediction_cache.get(cache_key)

        # Generate new prediction
        start_time = time.time()

        try:
            prediction = self.ensemble_model.predict_trade_setup(
                crypto_name, market_data, rule_based_analysis
            )

            # Convert to dictionary for caching
            result = {
                'win_probability': prediction.final_win_probability,
                'confidence': prediction.final_confidence,
                'rule_based_score': prediction.rule_based_score,
                'ml_score': prediction.ml_score,
                'ensemble_method': prediction.ensemble_method,
                'feature_importance': prediction.feature_importance,
                'decision_factors': prediction.decision_factors,
                'prediction_timestamp': prediction.prediction_timestamp.isoformat(),
                'generated_at': datetime.now().isoformat()
            }

            # Cache the result
            self.prediction_cache[cache_key] = result
            self.cache_timestamps[cache_key] = datetime.now()

            # Update performance metrics
            prediction_time = time.time() - start_time
            self.prediction_count += 1
            self.avg_prediction_time = (self.avg_prediction_time * 0.9) + (prediction_time * 0.1)

            return result

        except Exception as e:
            print(f"Error generating prediction for {crypto_name}: {e}")
            return None

    def should_trade(self,
                    crypto_name: str,
                    market_data: Optional[Dict[str, Any]] = None,
                    rule_based_analysis: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """
        Determine if we should execute a trade based on ML predictions.

        Args:
            crypto_name: Cryptocurrency name
            market_data: Current market data
            rule_based_analysis: Rule-based analysis results

        Returns:
            (should_trade, reason)
        """

        prediction = self.get_prediction(crypto_name, market_data, rule_based_analysis)
        if not prediction:
            return False, "Prediction failed"

        # Create ensemble prediction object from dict
        from poly_market_trader.ml.models.ensemble import EnsemblePrediction
        ensemble_pred = EnsemblePrediction(
            final_win_probability=prediction['win_probability'],
            final_confidence=prediction['confidence'],
            rule_based_score=prediction['rule_based_score'],
            ml_score=prediction['ml_score'],
            ensemble_method=prediction['ensemble_method'],
            feature_importance=prediction['feature_importance'],
            decision_factors=prediction['decision_factors'],
            prediction_timestamp=datetime.fromisoformat(prediction['prediction_timestamp'])
        )

        return self.ensemble_model.should_trade(ensemble_pred)

    def calculate_position_size(self,
                              crypto_name: str,
                              portfolio_value: float,
                              market_data: Optional[Dict[str, Any]] = None,
                              rule_based_analysis: Optional[Dict[str, Any]] = None) -> Tuple[float, str]:
        """
        Calculate optimal position size based on ML predictions.

        Args:
            crypto_name: Cryptocurrency name
            portfolio_value: Current portfolio value
            market_data: Current market data
            rule_based_analysis: Rule-based analysis results

        Returns:
            (position_size, reasoning)
        """

        prediction = self.get_prediction(crypto_name, market_data, rule_based_analysis)
        if not prediction:
            return 0.0, "Prediction failed"

        # Create ensemble prediction object from dict
        from poly_market_trader.ml.models.ensemble import EnsemblePrediction
        ensemble_pred = EnsemblePrediction(
            final_win_probability=prediction['win_probability'],
            final_confidence=prediction['confidence'],
            rule_based_score=prediction['rule_based_score'],
            ml_score=prediction['ml_score'],
            ensemble_method=prediction['ensemble_method'],
            feature_importance=prediction['feature_importance'],
            decision_factors=prediction['decision_factors'],
            prediction_timestamp=datetime.fromisoformat(prediction['prediction_timestamp'])
        )

        return self.ensemble_model.calculate_position_size(ensemble_pred, portfolio_value)

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached prediction is still valid"""
        if cache_key not in self.cache_timestamps:
            return False

        age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
        return age < self.cache_ttl

    def _background_update_loop(self):
        """Background thread for periodic model updates and maintenance"""
        while self.running:
            try:
                # Clean old cache entries
                self._clean_cache()

                # Could add model retraining logic here in the future

                time.sleep(self.update_interval)

            except Exception as e:
                print(f"Error in background update loop: {e}")
                time.sleep(self.update_interval)

    def _clean_cache(self):
        """Remove expired cache entries"""
        current_time = datetime.now()
        expired_keys = []

        for key, timestamp in self.cache_timestamps.items():
            age = (current_time - timestamp).total_seconds()
            if age > self.cache_ttl * 2:  # Keep entries a bit longer than TTL
                expired_keys.append(key)

        for key in expired_keys:
            self.prediction_cache.pop(key, None)
            self.cache_timestamps.pop(key, None)

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring"""
        cache_size = len(self.prediction_cache)

        return {
            'prediction_count': self.prediction_count,
            'cache_size': cache_size,
            'cache_hit_rate': self.cache_hit_rate,
            'avg_prediction_time': self.avg_prediction_time,
            'model_status': self.ensemble_model.get_model_status(),
            'last_update': datetime.now().isoformat()
        }

    def reset_cache(self):
        """Clear all cached predictions"""
        self.prediction_cache.clear()
        self.cache_timestamps.clear()
        print("Prediction cache cleared")

    def update_model_weights(self, rule_weight: float, ml_weight: float):
        """
        Update ensemble model weights dynamically.

        Args:
            rule_weight: New weight for rule-based predictions (0-1)
            ml_weight: New weight for ML predictions (0-1)
        """
        if abs(rule_weight + ml_weight - 1.0) > 0.01:
            print("Warning: Weights should sum to 1.0")
            return

        self.ensemble_model.rule_weight = rule_weight
        self.ensemble_model.ml_weight = ml_weight
        self.reset_cache()  # Clear cache since weights changed

        print(f"Model weights updated: Rule={rule_weight:.2f}, ML={ml_weight:.2f}")


class PredictionMonitor:
    """
    Monitor and log prediction performance for continuous improvement.
    Tracks prediction accuracy and model drift.
    """

    def __init__(self, log_file: str = "poly_market_trader/ml/logs/prediction_performance.jsonl"):
        """
        Initialize prediction monitor.

        Args:
            log_file: Path to log file for prediction performance
        """
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Performance tracking
        self.total_predictions = 0
        self.accurate_predictions = 0
        self.recent_predictions = []  # Keep last 100 predictions for rolling accuracy

    def log_prediction(self,
                      prediction: Dict[str, Any],
                      trade_executed: bool,
                      actual_outcome: Optional[bool] = None):
        """
        Log a prediction for performance tracking.

        Args:
            prediction: Prediction result dictionary
            trade_executed: Whether the trade was actually executed
            actual_outcome: Actual win/loss outcome (None if not yet known)
        """

        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'prediction': prediction,
            'trade_executed': trade_executed,
            'actual_outcome': actual_outcome,
            'logged_at': datetime.now().isoformat()
        }

        # Write to log file
        with open(self.log_file, 'a') as f:
            json.dump(log_entry, f)
            f.write('\n')

        # Update rolling statistics
        self.total_predictions += 1

        if actual_outcome is not None:
            self.recent_predictions.append(actual_outcome)
            if len(self.recent_predictions) > 100:
                self.recent_predictions.pop(0)

            predicted_win = prediction.get('win_probability', 0.5) > 0.5
            if predicted_win == actual_outcome:
                self.accurate_predictions += 1

    def get_accuracy_stats(self) -> Dict[str, float]:
        """Get current accuracy statistics"""
        if not self.recent_predictions:
            return {'overall_accuracy': 0.0, 'recent_accuracy': 0.0}

        recent_accuracy = np.mean(self.recent_predictions) if self.recent_predictions else 0.0
        overall_accuracy = self.accurate_predictions / max(self.total_predictions, 1)

        return {
            'overall_accuracy': overall_accuracy,
            'recent_accuracy': recent_accuracy,
            'total_predictions': self.total_predictions,
            'recent_predictions': len(self.recent_predictions)
        }

    def analyze_prediction_drift(self) -> Dict[str, Any]:
        """Analyze if model predictions are drifting over time"""
        # Read recent log entries and analyze trends
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()[-200:]  # Last 200 predictions

            predictions = []
            for line in lines:
                try:
                    entry = json.loads(line.strip())
                    pred = entry['prediction']
                    predictions.append({
                        'win_prob': pred.get('win_probability', 0.5),
                        'confidence': pred.get('confidence', 0.5),
                        'timestamp': entry['timestamp']
                    })
                except:
                    continue

            if len(predictions) < 20:
                return {'drift_detected': False, 'reason': 'Insufficient data'}

            # Analyze trends in confidence and win probability
            win_probs = [p['win_prob'] for p in predictions]
            confidences = [p['confidence'] for p in predictions]

            # Simple drift detection: check if recent predictions differ significantly
            recent_window = 50
            if len(predictions) >= recent_window:
                recent_win_probs = win_probs[-recent_window:]
                older_win_probs = win_probs[:-recent_window]

                recent_mean = np.mean(recent_win_probs)
                older_mean = np.mean(older_win_probs)

                drift_threshold = 0.1  # 10% change in average win probability
                if abs(recent_mean - older_mean) > drift_threshold:
                    return {
                        'drift_detected': True,
                        'drift_type': 'win_probability_shift',
                        'recent_mean': recent_mean,
                        'older_mean': older_mean,
                        'magnitude': abs(recent_mean - older_mean)
                    }

            return {'drift_detected': False, 'reason': 'No significant drift detected'}

        except Exception as e:
            return {'drift_detected': False, 'reason': f'Analysis error: {e}'}