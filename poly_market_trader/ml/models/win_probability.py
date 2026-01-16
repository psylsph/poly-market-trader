"""
Win probability classification model for Polymarket trading.
Predicts the likelihood of a trade being profitable based on technical and market features.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import os
import sys

# Optional imports for ML libraries
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score, classification_report
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier
    import joblib
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False
    joblib = None
    print("Warning: ML libraries not available. Win probability model will use fallback logic.")

from poly_market_trader.ml.features.feature_engineer import FeatureEngineer


@dataclass
class ModelMetrics:
    """Performance metrics for the win probability model"""
    accuracy: float
    precision: float
    recall: float
    roc_auc: float
    cross_val_score: float
    feature_importance: Dict[str, float]


@dataclass
class WinPrediction:
    """Prediction result from win probability model"""
    win_probability: float
    confidence_score: float
    feature_contributions: Dict[str, float]
    prediction_timestamp: datetime


class WinProbabilityModel:
    """
    Machine learning model to predict trade win probability.
    Uses ensemble of Random Forest and XGBoost for robust predictions.
    """

    def __init__(self, model_path: Optional[str] = None, feature_engineer: Optional[FeatureEngineer] = None):
        """
        Initialize win probability model.

        Args:
            model_path: Path to saved model file
            feature_engineer: Feature engineering instance
        """
        self.model_path = model_path or "poly_market_trader/ml/models/win_probability.joblib"
        self.feature_engineer = feature_engineer or FeatureEngineer()
        self.models = {}
        self.scaler = None
        self.feature_names = []
        self.is_trained = False

        if HAS_ML_LIBS and os.path.exists(self.model_path):
            self.load_model()

    def train(self, historical_trades: List[Dict[str, Any]], validation_split: float = 0.2) -> ModelMetrics:
        """
        Train the win probability model on historical trade data.

        Args:
            historical_trades: List of trade dictionaries with features and outcomes
            validation_split: Fraction of data for validation

        Returns:
            Training performance metrics
        """
        if not HAS_ML_LIBS:
            print("ML libraries not available, skipping training")
            return self._create_empty_metrics()

        if not historical_trades:
            print("No historical trades provided for training")
            return self._create_empty_metrics()

        # Extract features and labels
        features_list = []
        labels = []

        for trade in historical_trades:
            try:
                # Extract features for this trade
                crypto_name = trade.get('crypto_name', 'bitcoin')
                market_data = trade.get('market_data', {})

                features = self.feature_engineer.extract_features(crypto_name, market_data)
                features_list.append(features)

                # Determine outcome (win/loss)
                outcome = 1 if trade.get('status') == 'won' else 0
                labels.append(outcome)

            except Exception as e:
                print(f"Error processing trade: {e}")
                continue

        if len(features_list) < 10:
            print(f"Insufficient training data: {len(features_list)} samples")
            return self._create_empty_metrics()

        # Prepare feature matrix
        X, self.feature_names = self.feature_engineer.prepare_feature_matrix(features_list)
        y = np.array(labels)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=validation_split, random_state=42, stratify=y
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train ensemble of models
        self.models = {}

        # Random Forest
        rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            class_weight='balanced'
        )
        rf_model.fit(X_train_scaled, y_train)
        self.models['random_forest'] = rf_model

        # XGBoost
        xgb_model = XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42,
            scale_pos_weight=len(y_train[y_train==0]) / len(y_train[y_train==1])  # Handle class imbalance
        )
        xgb_model.fit(X_train_scaled, y_train)
        self.models['xgboost'] = xgb_model

        # Gradient Boosting
        gb_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
        gb_model.fit(X_train_scaled, y_train)
        self.models['gradient_boosting'] = gb_model

        self.is_trained = True

        # Calculate metrics
        metrics = self._evaluate_models(X_test_scaled, y_test)

        # Save model
        self.save_model()

        return metrics

    def predict(self, crypto_name: str, market_data: Optional[Dict[str, Any]] = None) -> WinPrediction:
        """
        Predict win probability for a potential trade setup.

        Args:
            crypto_name: Cryptocurrency name
            market_data: Current market data

        Returns:
            Win probability prediction
        """
        if not self.is_trained or not HAS_ML_LIBS:
            # Fallback to rule-based estimation
            return self._rule_based_prediction(crypto_name, market_data)

        try:
            # Extract features
            features = self.feature_engineer.extract_features(crypto_name, market_data)

            # Prepare feature matrix
            feature_values = []
            for name in self.feature_names:
                feature_values.append(features.get(name, 0.0))

            X = np.array([feature_values])

            if self.scaler:
                X_scaled = self.scaler.transform(X)
            else:
                X_scaled = X

            # Get predictions from all models
            predictions = {}
            probabilities = {}

            for model_name, model in self.models.items():
                pred_proba = model.predict_proba(X_scaled)[0]
                predictions[model_name] = pred_proba[1]  # Probability of win (class 1)
                probabilities[model_name] = pred_proba

            # Ensemble prediction (weighted average)
            weights = {'random_forest': 0.4, 'xgboost': 0.4, 'gradient_boosting': 0.2}
            win_probability = sum(predictions[model] * weights.get(model, 0.33)
                                 for model in predictions.keys())

            # Confidence score based on prediction consensus
            pred_std = np.std(list(predictions.values()))
            confidence_score = max(0.1, 1.0 - pred_std)  # Lower std = higher confidence

            # Feature contributions (simplified - would need SHAP for full implementation)
            feature_contributions = self._calculate_feature_contributions(features)

            return WinPrediction(
                win_probability=win_probability,
                confidence_score=confidence_score,
                feature_contributions=feature_contributions,
                prediction_timestamp=datetime.now()
            )

        except Exception as e:
            print(f"Error in prediction: {e}")
            return self._rule_based_prediction(crypto_name, market_data)

    def _rule_based_prediction(self, crypto_name: str, market_data: Optional[Dict[str, Any]] = None) -> WinPrediction:
        """Fallback rule-based prediction when ML is unavailable"""
        # Simple rule-based estimation based on current strategy logic
        features = self.feature_engineer.extract_features(crypto_name, market_data)

        # Estimate win probability based on key indicators
        adx = features.get('adx_15m', 25.0)
        bb_percent = features.get('bb_percent_b_15m', 0.5)
        rsi = features.get('rsi_15m', 50.0)

        # Base probability
        win_prob = 0.5

        # Adjust based on strong signals
        if adx <= 25:  # Weak trend (good for mean reversion)
            win_prob += 0.1

        if bb_percent < 0.15 and rsi < 35:  # Strong oversold signal
            win_prob += 0.15
        elif bb_percent > 0.85 and rsi > 65:  # Strong overbought signal
            win_prob += 0.15

        win_prob = max(0.1, min(0.9, win_prob))  # Clamp to reasonable range

        return WinPrediction(
            win_probability=win_prob,
            confidence_score=0.5,  # Medium confidence for rule-based
            feature_contributions={
                'adx_15m': (25 - adx) * 0.01,  # Positive contribution for weak trend
                'bb_percent_b_15m': 0.1 if bb_percent < 0.15 or bb_percent > 0.85 else 0.0,
                'rsi_15m': 0.1 if rsi < 35 or rsi > 65 else 0.0
            },
            prediction_timestamp=datetime.now()
        )

    def _calculate_feature_contributions(self, features: Dict[str, float]) -> Dict[str, float]:
        """Calculate approximate feature contributions (simplified version)"""
        contributions = {}

        # Key features that influence win probability
        if 'adx_15m' in features:
            adx = features['adx_15m']
            contributions['adx_15m'] = max(-0.1, (25 - adx) * 0.005)  # Positive for weak trends

        if 'bb_percent_b_15m' in features:
            bb_pos = features['bb_percent_b_15m']
            if bb_pos < 0.15 or bb_pos > 0.85:
                contributions['bb_percent_b_15m'] = 0.1
            else:
                contributions['bb_percent_b_15m'] = 0.0

        if 'rsi_15m' in features:
            rsi = features['rsi_15m']
            if rsi < 35 or rsi > 65:
                contributions['rsi_15m'] = 0.1
            else:
                contributions['rsi_15m'] = 0.0

        return contributions

    def _evaluate_models(self, X_test: np.ndarray, y_test: np.ndarray) -> ModelMetrics:
        """Evaluate trained models on test data"""
        if not self.models:
            return self._create_empty_metrics()

        # Use ensemble predictions for evaluation
        predictions = []
        probabilities = []

        for i in range(len(X_test)):
            sample = X_test[i:i+1]
            pred_proba = []

            for model_name, model in self.models.items():
                proba = model.predict_proba(sample)[0][1]
                pred_proba.append(proba)

            # Ensemble prediction
            ensemble_proba = np.mean(pred_proba)
            predictions.append(1 if ensemble_proba > 0.5 else 0)
            probabilities.append(ensemble_proba)

        predictions = np.array(predictions)
        probabilities = np.array(probabilities)

        # Calculate metrics
        accuracy = accuracy_score(y_test, predictions)
        precision = precision_score(y_test, predictions, zero_division=0)
        recall = recall_score(y_test, predictions, zero_division=0)
        roc_auc = roc_auc_score(y_test, probabilities) if len(np.unique(y_test)) > 1 else 0.5

        # Cross-validation score (simplified)
        cv_scores = []
        for model_name, model in self.models.items():
            try:
                scores = cross_val_score(model, X_test, y_test, cv=3, scoring='accuracy')
                cv_scores.append(np.mean(scores))
            except:
                cv_scores.append(0.5)
        cross_val_score = np.mean(cv_scores)

        # Feature importance (from Random Forest as example)
        rf_model = self.models.get('random_forest')
        if rf_model and hasattr(rf_model, 'feature_importances_'):
            feature_importance = dict(zip(self.feature_names, rf_model.feature_importances_))
        else:
            feature_importance = {}

        return ModelMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            roc_auc=roc_auc,
            cross_val_score=cross_val_score,
            feature_importance=feature_importance
        )

    def _create_empty_metrics(self) -> ModelMetrics:
        """Create empty metrics for error cases"""
        return ModelMetrics(
            accuracy=0.5,
            precision=0.5,
            recall=0.5,
            roc_auc=0.5,
            cross_val_score=0.5,
            feature_importance={}
        )

    def save_model(self):
        """Save trained model to disk"""
        if not self.is_trained:
            return

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        model_data = {
            'models': self.models,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained,
            'trained_at': datetime.now().isoformat()
        }

        joblib.dump(model_data, self.model_path)
        print(f"Model saved to {self.model_path}")

    def load_model(self):
        """Load trained model from disk"""
        try:
            model_data = joblib.load(self.model_path)
            self.models = model_data.get('models', {})
            self.scaler = model_data.get('scaler')
            self.feature_names = model_data.get('feature_names', [])
            self.is_trained = model_data.get('is_trained', False)
            print(f"Model loaded from {self.model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.is_trained = False