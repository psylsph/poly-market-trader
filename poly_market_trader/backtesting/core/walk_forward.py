"""
Walk-forward analysis system for strategy optimization and validation.
Implements rolling optimization windows to reduce overfitting bias.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional, Callable
from datetime import datetime, timedelta
import json
import os
from dataclasses import dataclass


@dataclass
class WalkForwardResult:
    """Result of a single walk-forward window"""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    optimal_params: Dict[str, Any]
    train_performance: Dict[str, float]
    test_performance: Dict[str, float]
    trades: List[Dict[str, Any]]


@dataclass
class WalkForwardSummary:
    """Summary statistics across all walk-forward windows"""
    total_windows: int
    avg_train_performance: Dict[str, float]
    avg_test_performance: Dict[str, float]
    test_performance_std: Dict[str, float]
    parameter_stability: Dict[str, float]
    overall_score: float


class WalkForwardAnalyzer:
    """
    Implements walk-forward analysis for strategy optimization.
    Uses rolling windows to train on past data and test on future data.
    """

    def __init__(self,
                 train_window_months: int = 3,
                 test_window_months: int = 1,
                 step_months: int = 1,
                 min_train_periods: int = 100):
        """
        Initialize walk-forward analyzer.

        Args:
            train_window_months: Months of data for training/optimization
            test_window_months: Months of data for out-of-sample testing
            step_months: Months to advance each window
            min_train_periods: Minimum data points required for training
        """
        self.train_window_months = train_window_months
        self.test_window_months = test_window_months
        self.step_months = step_months
        self.min_train_periods = min_train_periods

    def run_analysis(self,
                    historical_data: pd.DataFrame,
                    strategy_function: Callable,
                    parameter_ranges: Dict[str, List[Any]],
                    optimization_metric: str = 'sharpe_ratio') -> Tuple[List[WalkForwardResult], WalkForwardSummary]:
        """
        Run complete walk-forward analysis.

        Args:
            historical_data: OHLCV data with datetime index
            strategy_function: Function that takes params and returns performance dict
            parameter_ranges: Dict of parameter names to lists of values to test
            optimization_metric: Metric to optimize (sharpe_ratio, win_rate, profit_factor)

        Returns:
            List of walk-forward results and summary statistics
        """

        # Sort data by date
        historical_data = historical_data.sort_index()

        # Generate analysis windows
        windows = self._generate_windows(historical_data)

        results = []

        for window in windows:
            train_data = historical_data[window['train_start']:window['train_end']]
            test_data = historical_data[window['test_start']:window['test_end']]

            if len(train_data) < self.min_train_periods:
                continue

            # Optimize parameters on training data
            optimal_params = self._optimize_parameters(
                train_data, strategy_function, parameter_ranges, optimization_metric
            )

            # Evaluate on training data with optimal params
            train_performance = strategy_function(train_data, optimal_params)

            # Evaluate on test data with optimal params
            test_performance = strategy_function(test_data, optimal_params)

            # Get trade details from test period
            trades = self._extract_trades(strategy_function, test_data, optimal_params)

            result = WalkForwardResult(
                train_start=window['train_start'],
                train_end=window['train_end'],
                test_start=window['test_start'],
                test_end=window['test_end'],
                optimal_params=optimal_params,
                train_performance=train_performance,
                test_performance=test_performance,
                trades=trades
            )

            results.append(result)

        # Generate summary statistics
        summary = self._calculate_summary(results)

        return results, summary

    def _generate_windows(self, data: pd.DataFrame) -> List[Dict[str, datetime]]:
        """Generate train/test windows for walk-forward analysis"""
        windows = []

        start_date = data.index.min()
        end_date = data.index.max()

        current_train_end = start_date + pd.DateOffset(months=self.train_window_months)

        while current_train_end + pd.DateOffset(months=self.test_window_months) <= end_date:
            train_start = current_train_end - pd.DateOffset(months=self.train_window_months)
            train_end = current_train_end
            test_start = current_train_end
            test_end = current_train_end + pd.DateOffset(months=self.test_window_months)

            windows.append({
                'train_start': train_start,
                'train_end': train_end,
                'test_start': test_start,
                'test_end': test_end
            })

            current_train_end += pd.DateOffset(months=self.step_months)

        return windows

    def _optimize_parameters(self,
                           data: pd.DataFrame,
                           strategy_function: Callable,
                           parameter_ranges: Dict[str, List[Any]],
                           optimization_metric: str) -> Dict[str, Any]:
        """Find optimal parameter combination using grid search"""

        # Generate all parameter combinations
        param_names = list(parameter_ranges.keys())
        param_values = list(parameter_ranges.values())

        best_params = {}
        best_score = float('-inf')

        # Simple grid search (can be enhanced with more sophisticated optimization)
        for param_combo in np.ndindex(*[len(v) for v in param_values]):
            params = {name: param_values[i][combo_idx]
                     for i, (name, combo_idx) in enumerate(zip(param_names, param_combo))}

            performance = strategy_function(data, params)

            score = performance.get(optimization_metric, 0)

            if score > best_score:
                best_score = score
                best_params = params.copy()

        return best_params

    def _extract_trades(self,
                       strategy_function: Callable,
                       data: pd.DataFrame,
                       params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract detailed trade information from strategy execution"""
        # This would need to be implemented based on how the strategy function returns trade data
        # For now, return empty list - will be enhanced when integrated with actual strategy
        return []

    def _calculate_summary(self, results: List[WalkForwardResult]) -> WalkForwardSummary:
        """Calculate summary statistics across all walk-forward windows"""

        if not results:
            return WalkForwardSummary(0, {}, {}, {}, {}, 0.0)

        # Extract performance metrics
        train_metrics = {}
        test_metrics = {}
        param_values = {}

        for result in results:
            for key, value in result.train_performance.items():
                if key not in train_metrics:
                    train_metrics[key] = []
                train_metrics[key].append(value)

            for key, value in result.test_performance.items():
                if key not in test_metrics:
                    test_metrics[key] = []
                test_metrics[key].append(value)

            for key, value in result.optimal_params.items():
                if key not in param_values:
                    param_values[key] = []
                param_values[key].append(value)

        # Calculate averages and standard deviations
        avg_train = {k: np.mean(v) for k, v in train_metrics.items()}
        avg_test = {k: np.mean(v) for k, v in test_metrics.items()}
        test_std = {k: np.std(v) for k, v in test_metrics.items()}

        # Calculate parameter stability (coefficient of variation)
        param_stability = {}
        for param, values in param_values.items():
            if len(values) > 1:
                mean_val = np.mean(values)
                std_val = np.std(values)
                cv = std_val / mean_val if mean_val != 0 else float('inf')
                param_stability[param] = cv
            else:
                param_stability[param] = 0.0

        # Overall score: average test performance minus instability penalty
        test_win_rate = avg_test.get('win_rate', 0)
        test_sharpe = avg_test.get('sharpe_ratio', 0)
        param_instability = np.mean(list(param_stability.values())) if param_stability else 0

        overall_score = (test_win_rate * 0.6 + test_sharpe * 0.4) - (param_instability * 0.1)

        return WalkForwardSummary(
            total_windows=len(results),
            avg_train_performance=avg_train,
            avg_test_performance=avg_test,
            test_performance_std=test_std,
            parameter_stability=param_stability,
            overall_score=overall_score
        )

    def save_results(self, results: List[WalkForwardResult], summary: WalkForwardSummary, filepath: str):
        """Save walk-forward analysis results to JSON file"""

        # Convert datetime objects to strings
        results_dict = []
        for result in results:
            result_dict = {
                'train_start': result.train_start.isoformat(),
                'train_end': result.train_end.isoformat(),
                'test_start': result.test_start.isoformat(),
                'test_end': result.test_end.isoformat(),
                'optimal_params': result.optimal_params,
                'train_performance': result.train_performance,
                'test_performance': result.test_performance,
                'trades': result.trades
            }
            results_dict.append(result_dict)

        summary_dict = {
            'total_windows': summary.total_windows,
            'avg_train_performance': summary.avg_train_performance,
            'avg_test_performance': summary.avg_test_performance,
            'test_performance_std': summary.test_performance_std,
            'parameter_stability': summary.parameter_stability,
            'overall_score': summary.overall_score
        }

        output = {
            'results': results_dict,
            'summary': summary_dict,
            'generated_at': datetime.now().isoformat()
        }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)