"""
Monte Carlo simulation framework for strategy robustness testing.
Generates thousands of simulated equity curves to assess strategy stability.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Callable, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import json
import os


@dataclass
class MonteCarloResult:
    """Result of a single Monte Carlo simulation run"""
    run_id: int
    final_equity: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    equity_curve: List[float]
    trade_log: List[Dict[str, Any]]


@dataclass
class MonteCarloSummary:
    """Summary statistics across all Monte Carlo simulations"""
    total_runs: int
    avg_final_equity: float
    median_final_equity: float
    std_final_equity: float
    avg_total_return: float
    avg_max_drawdown: float
    avg_sharpe_ratio: float
    avg_win_rate: float
    percentile_5th: float
    percentile_95th: float
    confidence_interval_95: Tuple[float, float]
    success_rate: float  # % of runs with positive return
    robustness_score: float  # Overall stability metric


class MonteCarloSimulator:
    """
    Monte Carlo simulation framework for testing strategy robustness.
    Generates multiple simulated runs with randomized conditions.
    """

    def __init__(self,
                 num_simulations: int = 1000,
                 random_seed: Optional[int] = None):
        """
        Initialize Monte Carlo simulator.

        Args:
            num_simulations: Number of simulation runs to perform
            random_seed: Random seed for reproducible results
        """
        self.num_simulations = num_simulations
        self.random_seed = random_seed

        if random_seed is not None:
            np.random.seed(random_seed)
            random.seed(random_seed)

    def run_simulations(self,
                       historical_data: pd.DataFrame,
                       strategy_function: Callable,
                       strategy_params: Dict[str, Any],
                       noise_factors: Optional[Dict[str, float]] = None) -> Tuple[List[MonteCarloResult], MonteCarloSummary]:
        """
        Run Monte Carlo simulations with randomized conditions.

        Args:
            historical_data: Historical OHLCV data
            strategy_function: Function that executes strategy and returns results
            strategy_params: Base strategy parameters
            noise_factors: Dictionary of noise factors to apply (slippage, timing, etc.)

        Returns:
            List of individual simulation results and summary statistics
        """

        default_noise = {
            'slippage_std': 0.001,      # 0.1% standard deviation for slippage
            'timing_noise_std': 0.5,    # 0.5 period standard deviation for entry timing
            'price_noise_std': 0.002,   # 0.2% standard deviation for price variations
            'volume_noise_factor': 0.1, # 10% volume variation
        }

        noise_factors = noise_factors or default_noise

        results = []

        for run_id in range(self.num_simulations):
            # Create randomized version of strategy parameters
            randomized_params = self._add_parameter_noise(strategy_params.copy(), noise_factors)

            # Run strategy with noise
            noisy_data = self._add_market_noise(historical_data.copy(), noise_factors)

            # Execute strategy
            run_result = self._run_single_simulation(
                run_id, noisy_data, strategy_function, randomized_params
            )

            results.append(run_result)

        # Calculate summary statistics
        summary = self._calculate_summary(results)

        return results, summary

    def _add_parameter_noise(self, params: Dict[str, Any], noise_factors: Dict[str, float]) -> Dict[str, Any]:
        """Add random noise to strategy parameters"""
        noisy_params = params.copy()

        # Add noise to numeric parameters
        for key, value in params.items():
            if isinstance(value, (int, float)):
                if key.endswith('_threshold') or key.endswith('_level'):
                    # Add small noise to threshold parameters
                    noise = np.random.normal(0, 0.05)  # 5% standard deviation
                    noisy_params[key] = value * (1 + noise)
                elif key.endswith('_period') or key.endswith('_length'):
                    # Add small integer noise to period parameters
                    noise = np.random.normal(0, 1)
                    noisy_params[key] = max(1, int(value + noise))
                elif key in ['adx_threshold', 'rsi_threshold']:
                    # Add small noise to indicator thresholds
                    noise = np.random.normal(0, 2)  # ±2 points
                    noisy_params[key] = max(0, value + noise)

        return noisy_params

    def _add_market_noise(self, data: pd.DataFrame, noise_factors: Dict[str, float]) -> pd.DataFrame:
        """Add realistic market noise to historical data"""
        noisy_data = data.copy()

        # Add price noise
        price_noise = np.random.normal(0, noise_factors['price_noise_std'], len(data))
        noisy_data['close'] *= (1 + price_noise)
        noisy_data['high'] *= (1 + price_noise * 0.5)  # Less noise on highs
        noisy_data['low'] *= (1 + price_noise * 0.5)   # Less noise on lows
        noisy_data['open'] *= (1 + price_noise * 0.3)  # Even less on opens

        # Add volume noise
        volume_noise = np.random.normal(1, noise_factors['volume_noise_factor'], len(data))
        volume_noise = np.clip(volume_noise, 0.1, 3.0)  # Reasonable bounds
        noisy_data['volume'] *= volume_noise

        # Ensure OHLC relationships are maintained
        for idx in noisy_data.index:
            high = max(noisy_data.loc[idx, ['open', 'high', 'low', 'close']])
            low = min(noisy_data.loc[idx, ['open', 'high', 'low', 'close']])
            noisy_data.loc[idx, 'high'] = high
            noisy_data.loc[idx, 'low'] = low

        return noisy_data

    def _run_single_simulation(self,
                             run_id: int,
                             data: pd.DataFrame,
                             strategy_function: Callable,
                             params: Dict[str, Any]) -> MonteCarloResult:
        """Run a single simulation and return results"""

        # Execute strategy (this would need to be adapted based on actual strategy interface)
        # For now, we'll simulate a basic result structure
        try:
            strategy_result = strategy_function(data, params)

            # Extract key metrics from strategy result
            final_equity = strategy_result.get('final_equity', 10000.0)
            total_return = strategy_result.get('total_return', 0.0)
            max_drawdown = strategy_result.get('max_drawdown', 0.0)
            sharpe_ratio = strategy_result.get('sharpe_ratio', 0.0)
            win_rate = strategy_result.get('win_rate', 0.5)
            total_trades = strategy_result.get('total_trades', 0)
            equity_curve = strategy_result.get('equity_curve', [10000.0])
            trade_log = strategy_result.get('trade_log', [])

        except Exception as e:
            # Fallback for simulation errors
            print(f"Simulation {run_id} failed: {e}")
            final_equity = 10000.0
            total_return = 0.0
            max_drawdown = 0.0
            sharpe_ratio = 0.0
            win_rate = 0.5
            total_trades = 0
            equity_curve = [10000.0]
            trade_log = []

        return MonteCarloResult(
            run_id=run_id,
            final_equity=final_equity,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            total_trades=total_trades,
            equity_curve=equity_curve,
            trade_log=trade_log
        )

    def _calculate_summary(self, results: List[MonteCarloResult]) -> MonteCarloSummary:
        """Calculate summary statistics across all simulation results"""

        if not results:
            return MonteCarloSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, (0, 0), 0, 0)

        final_equities = [r.final_equity for r in results]
        total_returns = [r.total_return for r in results]

        avg_final_equity = np.mean(final_equities)
        median_final_equity = np.median(final_equities)
        std_final_equity = np.std(final_equities)

        avg_total_return = np.mean(total_returns)
        avg_max_drawdown = np.mean([r.max_drawdown for r in results])
        avg_sharpe_ratio = np.mean([r.sharpe_ratio for r in results])
        avg_win_rate = np.mean([r.win_rate for r in results])

        percentile_5th = np.percentile(final_equities, 5)
        percentile_95th = np.percentile(final_equities, 95)

        # 95% confidence interval for final equity
        confidence_interval_95 = (
            avg_final_equity - 1.96 * std_final_equity / np.sqrt(len(results)),
            avg_final_equity + 1.96 * std_final_equity / np.sqrt(len(results))
        )

        # Success rate: percentage of runs with positive return
        success_rate = np.mean([1 if r.total_return > 0 else 0 for r in results]) * 100

        # Robustness score: combination of success rate, Sharpe ratio, and drawdown control
        robustness_score = (
            success_rate * 0.4 +
            avg_sharpe_ratio * 10 * 0.3 +  # Scale Sharpe to percentage
            (1 - avg_max_drawdown) * 100 * 0.3  # Convert drawdown to score
        )

        return MonteCarloSummary(
            total_runs=len(results),
            avg_final_equity=avg_final_equity,
            median_final_equity=median_final_equity,
            std_final_equity=std_final_equity,
            avg_total_return=avg_total_return,
            avg_max_drawdown=avg_max_drawdown,
            avg_sharpe_ratio=avg_sharpe_ratio,
            avg_win_rate=avg_win_rate,
            percentile_5th=percentile_5th,
            percentile_95th=percentile_95th,
            confidence_interval_95=confidence_interval_95,
            success_rate=success_rate,
            robustness_score=robustness_score
        )

    def save_results(self, results: List[MonteCarloResult], summary: MonteCarloSummary, filepath: str):
        """Save Monte Carlo simulation results to JSON file"""

        # Convert results to serializable format
        results_dict = []
        for result in results:
            result_dict = {
                'run_id': result.run_id,
                'final_equity': result.final_equity,
                'total_return': result.total_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades,
                'equity_curve': result.equity_curve,
                'trade_log': result.trade_log
            }
            results_dict.append(result_dict)

        summary_dict = {
            'total_runs': summary.total_runs,
            'avg_final_equity': summary.avg_final_equity,
            'median_final_equity': summary.median_final_equity,
            'std_final_equity': summary.std_final_equity,
            'avg_total_return': summary.avg_total_return,
            'avg_max_drawdown': summary.avg_max_drawdown,
            'avg_sharpe_ratio': summary.avg_sharpe_ratio,
            'avg_win_rate': summary.avg_win_rate,
            'percentile_5th': summary.percentile_5th,
            'percentile_95th': summary.percentile_95th,
            'confidence_interval_95': summary.confidence_interval_95,
            'success_rate': summary.success_rate,
            'robustness_score': summary.robustness_score
        }

        output = {
            'results': results_dict,
            'summary': summary_dict,
            'generated_at': datetime.now().isoformat(),
            'num_simulations': self.num_simulations
        }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)