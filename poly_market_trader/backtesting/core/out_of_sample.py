"""
Out-of-sample testing pipeline for unbiased strategy validation.
Ensures test data is never used during strategy development or optimization.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os
import hashlib


@dataclass
class OutOfSampleResult:
    """Result of out-of-sample testing"""
    strategy_name: str
    train_period: Tuple[datetime, datetime]
    test_period: Tuple[datetime, datetime]
    train_performance: Dict[str, float]
    test_performance: Dict[str, float]
    performance_degradation: float  # Train - Test performance delta
    overfitting_score: float  # Measure of overfitting
    data_hash: str  # Hash to ensure data integrity
    parameters_used: Dict[str, Any]


@dataclass
class OutOfSampleSummary:
    """Summary across multiple out-of-sample tests"""
    total_tests: int
    avg_performance_degradation: float
    avg_overfitting_score: float
    robustness_rating: str  # 'Excellent', 'Good', 'Poor', 'Unacceptable'
    recommendations: List[str]


class OutOfSampleTester:
    """
    Implements strict out-of-sample testing to prevent data leakage and overfitting.
    Ensures test data is never used during strategy development.
    """

    def __init__(self, out_of_sample_ratio: float = 0.3, random_seed: Optional[int] = None):
        """
        Initialize out-of-sample tester.

        Args:
            out_of_sample_ratio: Fraction of data to reserve for testing (e.g., 0.3 = 30%)
            random_seed: Random seed for reproducible splits
        """
        self.out_of_sample_ratio = out_of_sample_ratio
        self.random_seed = random_seed

        if random_seed is not None:
            np.random.seed(random_seed)

    def create_train_test_split(self,
                              historical_data: pd.DataFrame,
                              split_method: str = 'time_based',
                              custom_split_date: Optional[datetime] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create train/test split with strict data isolation.

        Args:
            historical_data: Full historical dataset
            split_method: 'time_based', 'random', or 'custom_date'
            custom_split_date: Specific date for time-based split

        Returns:
            Tuple of (train_data, test_data)
        """

        if split_method == 'time_based':
            return self._time_based_split(historical_data, custom_split_date)
        elif split_method == 'random':
            return self._random_split(historical_data)
        elif split_method == 'custom_date':
            return self._time_based_split(historical_data, custom_split_date)
        else:
            raise ValueError(f"Unknown split method: {split_method}")

    def _time_based_split(self,
                         data: pd.DataFrame,
                         split_date: Optional[datetime] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data chronologically to maintain time series integrity"""

        sorted_data = data.sort_index()

        if split_date is None:
            # Use percentage-based split
            split_idx = int(len(sorted_data) * (1 - self.out_of_sample_ratio))
            split_date = sorted_data.index[split_idx]

        train_data = sorted_data[sorted_data.index < split_date]
        test_data = sorted_data[sorted_data.index >= split_date]

        return train_data, test_data

    def _random_split(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Random split (not recommended for time series data)"""

        indices = np.random.permutation(len(data))
        split_idx = int(len(data) * (1 - self.out_of_sample_ratio))

        train_indices = indices[:split_idx]
        test_indices = indices[split_idx:]

        train_data = data.iloc[train_indices].sort_index()
        test_data = data.iloc[test_indices].sort_index()

        return train_data, test_data

    def run_out_of_sample_test(self,
                             strategy_function: Callable,
                             strategy_params: Dict[str, Any],
                             train_data: pd.DataFrame,
                             test_data: pd.DataFrame,
                             strategy_name: str = "unnamed_strategy") -> OutOfSampleResult:
        """
        Run complete out-of-sample test with performance comparison.

        Args:
            strategy_function: Strategy implementation function
            strategy_params: Strategy parameters
            train_data: Training dataset (used for optimization)
            test_data: Test dataset (never seen during development)
            strategy_name: Descriptive name for the strategy

        Returns:
            Complete out-of-sample test result
        """

        # Calculate data hash for integrity verification
        data_hash = self._calculate_data_hash(train_data, test_data)

        # Train period
        train_period = (train_data.index.min(), train_data.index.max())

        # Test period
        test_period = (test_data.index.min(), test_data.index.max())

        # Evaluate on training data
        train_performance = strategy_function(train_data, strategy_params)

        # Evaluate on test data (same parameters, different data)
        test_performance = strategy_function(test_data, strategy_params)

        # Calculate performance degradation
        performance_degradation = self._calculate_performance_degradation(
            train_performance, test_performance
        )

        # Calculate overfitting score
        overfitting_score = self._calculate_overfitting_score(
            train_performance, test_performance
        )

        return OutOfSampleResult(
            strategy_name=strategy_name,
            train_period=train_period,
            test_period=test_period,
            train_performance=train_performance,
            test_performance=test_performance,
            performance_degradation=performance_degradation,
            overfitting_score=overfitting_score,
            data_hash=data_hash,
            parameters_used=strategy_params
        )

    def _calculate_data_hash(self, train_data: pd.DataFrame, test_data: pd.DataFrame) -> str:
        """Calculate hash of train/test data for integrity verification"""
        combined_data = pd.concat([train_data, test_data]).sort_index()
        data_str = combined_data.to_csv().encode('utf-8')
        return hashlib.sha256(data_str).hexdigest()[:16]

    def _calculate_performance_degradation(self,
                                         train_perf: Dict[str, float],
                                         test_perf: Dict[str, float]) -> float:
        """Calculate how much performance degrades from train to test"""

        key_metrics = ['sharpe_ratio', 'win_rate', 'total_return', 'profit_factor']

        degradations = []
        for metric in key_metrics:
            if metric in train_perf and metric in test_perf:
                train_val = train_perf[metric]
                test_val = test_perf[metric]
                if train_val != 0:
                    degradation = (train_val - test_val) / abs(train_val)
                    degradations.append(degradation)

        return np.mean(degradations) if degradations else 0.0

    def _calculate_overfitting_score(self,
                                   train_perf: Dict[str, float],
                                   test_perf: Dict[str, float]) -> float:
        """Calculate overfitting score based on performance delta"""

        # Overfitting score: how much better training looks than testing
        # Higher score = more overfitting

        train_sharpe = train_perf.get('sharpe_ratio', 0)
        test_sharpe = test_perf.get('sharpe_ratio', 0)
        sharpe_delta = max(0, train_sharpe - test_sharpe)

        train_win_rate = train_perf.get('win_rate', 0)
        test_win_rate = test_perf.get('win_rate', 0)
        win_rate_delta = max(0, train_win_rate - test_win_rate)

        # Weighted combination
        overfitting_score = (sharpe_delta * 0.6 + win_rate_delta * 0.4)

        return overfitting_score

    def run_multiple_tests(self,
                          strategies: Dict[str, Tuple[Callable, Dict[str, Any]]],
                          historical_data: pd.DataFrame,
                          num_splits: int = 5) -> Tuple[List[OutOfSampleResult], OutOfSampleSummary]:
        """
        Run out-of-sample tests across multiple strategies and data splits.

        Args:
            strategies: Dict of strategy_name -> (strategy_function, strategy_params)
            historical_data: Full historical dataset
            num_splits: Number of different train/test splits to test

        Returns:
            List of results and summary statistics
        """

        all_results = []

        # Create multiple train/test splits
        for split_idx in range(num_splits):
            # Use different random seeds for different splits
            split_seed = self.random_seed + split_idx if self.random_seed else None
            if split_seed:
                np.random.seed(split_seed)

            # Create train/test split
            train_data, test_data = self.create_train_test_split(
                historical_data, split_method='time_based'
            )

            # Test each strategy on this split
            for strategy_name, (strategy_func, strategy_params) in strategies.items():
                result = self.run_out_of_sample_test(
                    strategy_func, strategy_params, train_data, test_data,
                    strategy_name=f"{strategy_name}_split_{split_idx}"
                )
                all_results.append(result)

        # Calculate summary
        summary = self._calculate_multi_test_summary(all_results)

        return all_results, summary

    def _calculate_multi_test_summary(self, results: List[OutOfSampleResult]) -> OutOfSampleSummary:
        """Calculate summary statistics across multiple out-of-sample tests"""

        if not results:
            return OutOfSampleSummary(0, 0, 0, 'Unknown', [])

        degradations = [r.performance_degradation for r in results]
        overfitting_scores = [r.overfitting_score for r in results]

        avg_degradation = np.mean(degradations)
        avg_overfitting = np.mean(overfitting_scores)

        # Determine robustness rating
        if avg_overfitting < 0.1 and avg_degradation < 0.2:
            robustness = 'Excellent'
        elif avg_overfitting < 0.2 and avg_degradation < 0.4:
            robustness = 'Good'
        elif avg_overfitting < 0.4 and avg_degradation < 0.6:
            robustness = 'Poor'
        else:
            robustness = 'Unacceptable'

        # Generate recommendations
        recommendations = []
        if avg_overfitting > 0.3:
            recommendations.append("High overfitting detected - simplify strategy or use more data")
        if avg_degradation > 0.5:
            recommendations.append("Significant performance degradation - strategy may be curve-fit")
        if robustness == 'Unacceptable':
            recommendations.append("Strategy shows unacceptable out-of-sample performance - reconsider approach")

        return OutOfSampleSummary(
            total_tests=len(results),
            avg_performance_degradation=avg_degradation,
            avg_overfitting_score=avg_overfitting,
            robustness_rating=robustness,
            recommendations=recommendations
        )

    def save_results(self, results: List[OutOfSampleResult], summary: OutOfSampleSummary, filepath: str):
        """Save out-of-sample test results to JSON file"""

        results_dict = []
        for result in results:
            result_dict = {
                'strategy_name': result.strategy_name,
                'train_period': [result.train_period[0].isoformat(), result.train_period[1].isoformat()],
                'test_period': [result.test_period[0].isoformat(), result.test_period[1].isoformat()],
                'train_performance': result.train_performance,
                'test_performance': result.test_performance,
                'performance_degradation': result.performance_degradation,
                'overfitting_score': result.overfitting_score,
                'data_hash': result.data_hash,
                'parameters_used': result.parameters_used
            }
            results_dict.append(result_dict)

        summary_dict = {
            'total_tests': summary.total_tests,
            'avg_performance_degradation': summary.avg_performance_degradation,
            'avg_overfitting_score': summary.avg_overfitting_score,
            'robustness_rating': summary.robustness_rating,
            'recommendations': summary.recommendations
        }

        output = {
            'results': results_dict,
            'summary': summary_dict,
            'generated_at': datetime.now().isoformat(),
            'out_of_sample_ratio': self.out_of_sample_ratio
        }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)