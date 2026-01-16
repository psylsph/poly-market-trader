"""
Comprehensive performance metrics calculator for trading strategies.
Provides risk-adjusted metrics, drawdown analysis, and statistical measures.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Optional imports for statistical functions
try:
    import scipy.stats as stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    stats = None


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a trading strategy"""
    # Basic return metrics
    total_return: float
    annualized_return: float
    volatility: float
    max_drawdown: float
    peak_to_valley: float

    # Risk-adjusted metrics
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float

    # Win/Loss metrics
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float

    # Trade statistics
    total_trades: int
    avg_trade_duration: Optional[float]
    best_trade: float
    worst_trade: float

    # Advanced metrics
    value_at_risk_95: float
    expected_shortfall_95: float
    ulcer_index: float
    serenity_index: float

    # Benchmark comparisons
    benchmark_return: float
    benchmark_volatility: float
    information_ratio: float
    beta: float
    alpha: float

    # Statistical tests
    normality_test_p_value: float
    autocorrelation_test: float


class PerformanceCalculator:
    """
    Calculates comprehensive performance metrics for trading strategies.
    Provides risk-adjusted measures, drawdown analysis, and statistical validation.
    """

    def __init__(self, risk_free_rate: float = 0.02, benchmark_returns: Optional[np.ndarray] = None):
        """
        Initialize performance calculator.

        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
            benchmark_returns: Benchmark returns array for comparison
        """
        self.risk_free_rate = risk_free_rate
        self.benchmark_returns = benchmark_returns or np.array([])

    def calculate_metrics(self,
                         equity_curve: np.ndarray,
                         trade_returns: Optional[np.ndarray] = None,
                         timestamps: Optional[np.ndarray] = None) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            equity_curve: Array of equity values over time
            trade_returns: Array of individual trade returns
            timestamps: Array of timestamps for time-based calculations

        Returns:
            Complete performance metrics
        """

        if len(equity_curve) < 2:
            return self._create_empty_metrics()

        # Calculate returns
        returns = np.diff(equity_curve) / equity_curve[:-1]

        # Basic metrics
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        annualized_return = self._annualize_return(total_return, len(returns))

        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        max_drawdown, peak_to_valley = self._calculate_max_drawdown(equity_curve)

        # Risk-adjusted metrics
        sharpe_ratio = self._calculate_sharpe_ratio(returns, annualized_return)
        sortino_ratio = self._calculate_sortino_ratio(returns, annualized_return)
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        omega_ratio = self._calculate_omega_ratio(returns)

        # Trade-based metrics
        if trade_returns is not None and len(trade_returns) > 0:
            win_rate, profit_factor, avg_win, avg_loss, largest_win, largest_loss = self._calculate_trade_metrics(trade_returns)
            total_trades = len(trade_returns)
            best_trade = np.max(trade_returns)
            worst_trade = np.min(trade_returns)
        else:
            win_rate = profit_factor = avg_win = avg_loss = 0
            largest_win = largest_loss = total_trades = 0
            best_trade = worst_trade = 0

        # Trade duration (if timestamps available)
        avg_trade_duration = self._calculate_avg_trade_duration(timestamps) if timestamps is not None else None

        # Advanced risk metrics
        value_at_risk_95 = self._calculate_var(returns, 0.05)
        expected_shortfall_95 = self._calculate_expected_shortfall(returns, 0.05)
        ulcer_index = self._calculate_ulcer_index(equity_curve)
        serenity_index = self._calculate_serenity_index(returns, max_drawdown)

        # Benchmark comparisons
        benchmark_metrics = self._calculate_benchmark_metrics(returns)

        # Statistical tests
        normality_test_p_value = self._test_normality(returns)
        autocorrelation_test = self._test_autocorrelation(returns)

        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            max_drawdown=max_drawdown,
            peak_to_valley=peak_to_valley,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            omega_ratio=omega_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            total_trades=total_trades,
            avg_trade_duration=avg_trade_duration,
            best_trade=best_trade,
            worst_trade=worst_trade,
            value_at_risk_95=value_at_risk_95,
            expected_shortfall_95=expected_shortfall_95,
            ulcer_index=ulcer_index,
            serenity_index=serenity_index,
            benchmark_return=benchmark_metrics['benchmark_return'],
            benchmark_volatility=benchmark_metrics['benchmark_volatility'],
            information_ratio=benchmark_metrics['information_ratio'],
            beta=benchmark_metrics['beta'],
            alpha=benchmark_metrics['alpha'],
            normality_test_p_value=normality_test_p_value,
            autocorrelation_test=autocorrelation_test
        )

    def _annualize_return(self, total_return: float, num_periods: int) -> float:
        """Annualize total return based on number of periods"""
        if num_periods <= 0:
            return 0
        # Assume daily returns for annualization
        return (1 + total_return) ** (252 / num_periods) - 1

    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> Tuple[float, float]:
        """Calculate maximum drawdown and peak-to-valley"""
        peak = equity_curve[0]
        max_drawdown = 0
        peak_to_valley = 0

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                peak_to_valley = peak - value

        return max_drawdown, peak_to_valley

    def _calculate_sharpe_ratio(self, returns: np.ndarray, annualized_return: float) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0

        excess_returns = returns - self.risk_free_rate / 252  # Daily risk-free rate
        if np.std(excess_returns) == 0:
            return 0

        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    def _calculate_sortino_ratio(self, returns: np.ndarray, annualized_return: float) -> float:
        """Calculate Sortino ratio (downside deviation only)"""
        if len(returns) < 2:
            return 0

        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf') if annualized_return > 0 else 0

        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return float('inf')

        return annualized_return / (downside_std * np.sqrt(252))

    def _calculate_omega_ratio(self, returns: np.ndarray, threshold: float = 0) -> float:
        """Calculate Omega ratio (gain/loss ratio above threshold)"""
        gains = returns[returns > threshold]
        losses = returns[returns <= threshold]

        if len(losses) == 0:
            return float('inf')
        if len(gains) == 0:
            return 0

        return np.sum(gains) / abs(np.sum(losses))

    def _calculate_trade_metrics(self, trade_returns: np.ndarray) -> Tuple[float, float, float, float, float, float]:
        """Calculate trade-based performance metrics"""
        if len(trade_returns) == 0:
            return 0, 0, 0, 0, 0, 0

        winning_trades = trade_returns[trade_returns > 0]
        losing_trades = trade_returns[trade_returns < 0]

        win_rate = len(winning_trades) / len(trade_returns)
        avg_win = np.mean(winning_trades) if len(winning_trades) > 0 else 0
        avg_loss = np.mean(losing_trades) if len(losing_trades) > 0 else 0
        largest_win = np.max(winning_trades) if len(winning_trades) > 0 else 0
        largest_loss = np.min(losing_trades) if len(losing_trades) > 0 else 0

        total_profit = np.sum(winning_trades)
        total_loss = abs(np.sum(losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        return win_rate, profit_factor, avg_win, avg_loss, largest_win, largest_loss

    def _calculate_avg_trade_duration(self, timestamps: np.ndarray) -> Optional[float]:
        """Calculate average trade duration in days"""
        if timestamps is None or len(timestamps) < 2:
            return None

        durations = np.diff(timestamps)
        return np.mean(durations).total_seconds() / (24 * 3600)  # Convert to days

    def _calculate_var(self, returns: np.ndarray, confidence: float = 0.05) -> float:
        """Calculate Value at Risk"""
        if len(returns) == 0:
            return 0
        return np.percentile(returns, confidence * 100)

    def _calculate_expected_shortfall(self, returns: np.ndarray, confidence: float = 0.05) -> float:
        """Calculate Expected Shortfall (Conditional VaR)"""
        if len(returns) == 0:
            return 0
        var_threshold = self._calculate_var(returns, confidence)
        tail_losses = returns[returns <= var_threshold]
        return np.mean(tail_losses) if len(tail_losses) > 0 else var_threshold

    def _calculate_ulcer_index(self, equity_curve: np.ndarray) -> float:
        """Calculate Ulcer Index (drawdown-based stress measure)"""
        if len(equity_curve) < 2:
            return 0

        # Calculate drawdowns
        peak = equity_curve[0]
        drawdowns = []

        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            drawdowns.append(drawdown)

        ulcer_index = np.sqrt(np.mean(np.array(drawdowns) ** 2))
        return ulcer_index

    def _calculate_serenity_index(self, returns: np.ndarray, max_drawdown: float) -> float:
        """Calculate Serenity Index (return per unit of drawdown)"""
        if max_drawdown == 0:
            return float('inf')

        annualized_return = self._annualize_return(np.prod(1 + returns) - 1, len(returns))
        return annualized_return / max_drawdown

    def _calculate_benchmark_metrics(self, returns: np.ndarray) -> Dict[str, float]:
        """Calculate benchmark comparison metrics"""
        if len(self.benchmark_returns) == 0 or len(returns) != len(self.benchmark_returns):
            return {
                'benchmark_return': 0,
                'benchmark_volatility': 0,
                'information_ratio': 0,
                'beta': 1,
                'alpha': 0
            }

        benchmark_return = np.prod(1 + self.benchmark_returns) - 1
        benchmark_volatility = np.std(self.benchmark_returns) * np.sqrt(252)

        # Calculate beta (market sensitivity)
        covariance = np.cov(returns, self.benchmark_returns)[0, 1]
        benchmark_variance = np.var(self.benchmark_returns)
        beta = covariance / benchmark_variance if benchmark_variance > 0 else 1

        # Calculate alpha (excess return)
        strategy_return = np.prod(1 + returns) - 1
        expected_return = self.risk_free_rate + beta * (benchmark_return - self.risk_free_rate)
        alpha = strategy_return - expected_return

        # Information ratio (active return / tracking error)
        active_returns = returns - self.benchmark_returns
        tracking_error = np.std(active_returns) * np.sqrt(252)
        information_ratio = np.mean(active_returns) * 252 / tracking_error if tracking_error > 0 else 0

        return {
            'benchmark_return': benchmark_return,
            'benchmark_volatility': benchmark_volatility,
            'information_ratio': information_ratio,
            'beta': beta,
            'alpha': alpha
        }

    def _test_normality(self, returns: np.ndarray) -> float:
        """Test if returns follow normal distribution (Shapiro-Wilk test)"""
        if len(returns) < 3 or not HAS_SCIPY:
            return 1.0  # Can't test with too few samples or no scipy

        try:
            _, p_value = stats.shapiro(returns)
            return p_value
        except:
            return 0.0  # Test failed

    def _test_autocorrelation(self, returns: np.ndarray) -> float:
        """Test for autocorrelation in returns (Ljung-Box test)"""
        if len(returns) < 10 or not HAS_SCIPY:
            return 0.0  # Need more data or scipy

        try:
            # Try to import statsmodels for Ljung-Box test
            from statsmodels.stats.diagnostic import acorr_ljungbox
            lb_test = acorr_ljungbox(returns, lags=[5], return_df=False)
            return lb_test[1][0]  # p-value
        except ImportError:
            # Fallback to simple autocorrelation test using numpy
            autocorr = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            return abs(autocorr)  # Return absolute correlation as rough indicator
        except:
            return 0.0  # Test failed

    def _create_empty_metrics(self) -> PerformanceMetrics:
        """Create empty metrics for invalid data"""
        return PerformanceMetrics(
            total_return=0, annualized_return=0, volatility=0, max_drawdown=0, peak_to_valley=0,
            sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0, omega_ratio=0,
            win_rate=0, profit_factor=0, avg_win=0, avg_loss=0, largest_win=0, largest_loss=0,
            total_trades=0, avg_trade_duration=None, best_trade=0, worst_trade=0,
            value_at_risk_95=0, expected_shortfall_95=0, ulcer_index=0, serenity_index=0,
            benchmark_return=0, benchmark_volatility=0, information_ratio=0, beta=1, alpha=0,
            normality_test_p_value=0, autocorrelation_test=0
        )

    def compare_strategies(self, metrics_list: List[PerformanceMetrics], strategy_names: List[str]) -> pd.DataFrame:
        """Compare multiple strategies side by side"""
        comparison_data = {}

        for i, metrics in enumerate(metrics_list):
            name = strategy_names[i] if i < len(strategy_names) else f"Strategy_{i}"
            comparison_data[f"{name}_sharpe"] = metrics.sharpe_ratio
            comparison_data[f"{name}_win_rate"] = metrics.win_rate
            comparison_data[f"{name}_max_dd"] = metrics.max_drawdown
            comparison_data[f"{name}_profit_factor"] = metrics.profit_factor
            comparison_data[f"{name}_total_return"] = metrics.total_return

        return pd.DataFrame(comparison_data)