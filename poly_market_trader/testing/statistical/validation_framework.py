"""
Statistical validation framework for trading strategy performance.
Provides hypothesis testing, confidence intervals, and significance analysis.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import json
import os

# Optional imports for statistical functions
try:
    import scipy.stats as stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    stats = None

try:
    from statsmodels.stats.power import TTestPower
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


@dataclass
class HypothesisTestResult:
    """Result of a hypothesis test"""
    test_name: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_statistic: float
    p_value: float
    significance_level: float
    reject_null: bool
    effect_size: Optional[float]
    confidence_interval: Tuple[float, float]
    sample_size: int
    power: Optional[float]


@dataclass
class StatisticalValidationReport:
    """Comprehensive statistical validation report"""
    win_rate_test: HypothesisTestResult
    sharpe_ratio_test: Optional[HypothesisTestResult]
    max_drawdown_test: Optional[HypothesisTestResult]
    overall_confidence: str  # 'High', 'Medium', 'Low', 'Insufficient'
    recommendations: List[str]
    statistical_power: float
    sample_size_assessment: str
    generated_at: datetime


class StatisticalValidator:
    """
    Comprehensive statistical validation for trading strategy performance.
    Tests for statistical significance of performance improvements.
    """

    def __init__(self, baseline_win_rate: float = 0.50, significance_level: float = 0.05):
        """
        Initialize statistical validator.

        Args:
            baseline_win_rate: Expected win rate under null hypothesis (default 50%)
            significance_level: Alpha level for hypothesis tests (default 5%)
        """
        self.baseline_win_rate = baseline_win_rate
        self.alpha = significance_level

    def validate_strategy_performance(self,
                                    trade_results: List[Dict[str, Any]],
                                    baseline_performance: Optional[Dict[str, float]] = None) -> StatisticalValidationReport:
        """
        Comprehensive statistical validation of strategy performance.

        Args:
            trade_results: List of trade result dictionaries
            baseline_performance: Optional baseline performance metrics

        Returns:
            Complete statistical validation report
        """

        # Extract trade outcomes
        outcomes = []
        returns = []

        for trade in trade_results:
            # Win/loss outcome
            if 'status' in trade:
                outcome = 1 if trade['status'] == 'won' else 0
            elif 'outcome' in trade:
                outcome = 1 if trade['outcome'] == 'win' else 0
            else:
                continue

            outcomes.append(outcome)

            # Return calculation
            if 'return' in trade:
                returns.append(trade['return'])
            elif 'pnl' in trade and 'cost' in trade and trade['cost'] > 0:
                returns.append(trade['pnl'] / trade['cost'])
            else:
                returns.append(0.0)

        if len(outcomes) < 10:
            return self._create_insufficient_data_report(len(outcomes))

        outcomes = np.array(outcomes)
        returns = np.array(returns)

        # Calculate observed performance
        observed_win_rate = np.mean(outcomes)
        observed_sharpe = self._calculate_sharpe_ratio(returns) if len(returns) > 1 else 0
        observed_max_dd = self._calculate_max_drawdown_from_returns(returns) if len(returns) > 1 else 0

        # Hypothesis tests
        win_rate_test = self._test_win_rate_improvement(outcomes, observed_win_rate)

        sharpe_test = None
        if len(returns) > 30:  # Need sufficient data for Sharpe test
            sharpe_test = self._test_sharpe_ratio_significance(returns, observed_sharpe)

        max_dd_test = None
        if len(returns) > 20:
            max_dd_test = self._test_max_drawdown_improvement(returns, observed_max_dd)

        # Overall assessment
        overall_confidence = self._assess_overall_confidence(
            win_rate_test, sharpe_test, max_dd_test, len(outcomes)
        )

        recommendations = self._generate_recommendations(
            win_rate_test, sharpe_test, max_dd_test, len(outcomes)
        )

        # Statistical power analysis
        statistical_power = self._calculate_statistical_power(len(outcomes), observed_win_rate)

        sample_assessment = self._assess_sample_size(len(outcomes), observed_win_rate)

        return StatisticalValidationReport(
            win_rate_test=win_rate_test,
            sharpe_ratio_test=sharpe_test,
            max_drawdown_test=max_dd_test,
            overall_confidence=overall_confidence,
            recommendations=recommendations,
            statistical_power=statistical_power,
            sample_size_assessment=sample_assessment,
            generated_at=datetime.now()
        )

    def _test_win_rate_improvement(self, outcomes: np.ndarray, observed_win_rate: float) -> HypothesisTestResult:
        """Test if observed win rate is significantly better than baseline"""

        n = len(outcomes)

        if not HAS_SCIPY:
            # Fallback approximation without scipy
            se = np.sqrt(self.baseline_win_rate * (1 - self.baseline_win_rate) / n)
            z_stat = (observed_win_rate - self.baseline_win_rate) / se
            # Approximate p-value using normal distribution CDF
            p_value = 0.5 * (1 + np.sign(z_stat) * np.sqrt(1 - np.exp(-2 * z_stat**2 / np.pi)))
            p_value = 1 - p_value if z_stat > 0 else p_value  # One-tailed
        else:
            # One-sample proportion test (z-test approximation)
            # H₀: π ≤ baseline_win_rate
            # H₁: π > baseline_win_rate

            se = np.sqrt(self.baseline_win_rate * (1 - self.baseline_win_rate) / n)
            z_stat = (observed_win_rate - self.baseline_win_rate) / se

            # One-tailed p-value
            p_value = 1 - stats.norm.cdf(z_stat)

        # Confidence interval (always available)
        ci_lower = observed_win_rate - 1.96 * np.sqrt(observed_win_rate * (1 - observed_win_rate) / n)
        ci_upper = observed_win_rate + 1.96 * np.sqrt(observed_win_rate * (1 - observed_win_rate) / n)

        # Effect size (Cohen's h for proportions)
        effect_size = (observed_win_rate - self.baseline_win_rate) / np.sqrt(
            (self.baseline_win_rate * (1 - self.baseline_win_rate) +
             observed_win_rate * (1 - observed_win_rate)) / 2
        )

        # Statistical power (if statsmodels available)
        power = None
        if HAS_STATSMODELS:
            try:
                analysis = TTestPower()
                # Convert to t-test equivalent for proportions
                power = analysis.solve_power(
                    effect_size=effect_size,
                    nobs=n,
                    alpha=self.alpha,
                    alternative='larger'
                )
            except:
                power = None

        return HypothesisTestResult(
            test_name="Win Rate Improvement Test",
            null_hypothesis=f"Win rate ≤ {self.baseline_win_rate:.1%}",
            alternative_hypothesis=f"Win rate > {self.baseline_win_rate:.1%}",
            test_statistic=z_stat,
            p_value=p_value,
            significance_level=self.alpha,
            reject_null=p_value < self.alpha,
            effect_size=effect_size,
            confidence_interval=(max(0, ci_lower), min(1, ci_upper)),
            sample_size=n,
            power=power
        )

    def _test_sharpe_ratio_significance(self, returns: np.ndarray, observed_sharpe: float) -> HypothesisTestResult:
        """Test if Sharpe ratio is significantly positive"""

        n = len(returns)

        if not HAS_SCIPY:
            # Simplified test without scipy
            # Use rule of thumb: Sharpe > 0.5 is generally considered good
            reject_null = observed_sharpe > 0.5
            p_value = 0.1 if observed_sharpe > 0.5 else 0.5  # Rough approximation
            t_stat = observed_sharpe
            ci_margin = observed_sharpe * 0.2  # 20% confidence interval approximation
        else:
            # Proper statistical test
            # H₀: Sharpe ≤ 0
            # H₁: Sharpe > 0

            # Calculate standard error of Sharpe ratio
            if n > 1:
                # Annualized Sharpe ratio standard error approximation
                se = np.sqrt((1 + 0.5 * observed_sharpe**2) / (n - 1)) * np.sqrt(252)
                t_stat = observed_sharpe / se
                p_value = 1 - stats.t.cdf(t_stat, n - 1)
            else:
                t_stat = 0
                p_value = 1.0

            reject_null = p_value < self.alpha
            ci_margin = 1.96 * (np.sqrt((1 + 0.5 * observed_sharpe**2) / (n - 1)) * np.sqrt(252))

        # Confidence interval
        ci_lower = observed_sharpe - ci_margin
        ci_upper = observed_sharpe + ci_margin

        return HypothesisTestResult(
            test_name="Sharpe Ratio Significance Test",
            null_hypothesis="Sharpe ratio ≤ 0",
            alternative_hypothesis="Sharpe ratio > 0",
            test_statistic=t_stat,
            p_value=p_value,
            significance_level=self.alpha,
            reject_null=reject_null,
            effect_size=observed_sharpe,  # Sharpe itself as effect size
            confidence_interval=(ci_lower, ci_upper),
            sample_size=n,
            power=None  # Would need more complex calculation
        )

    def _test_max_drawdown_improvement(self, returns: np.ndarray, observed_max_dd: float) -> HypothesisTestResult:
        """Test if max drawdown is within acceptable bounds"""

        # This is more of a validation test than a hypothesis test
        # H₀: Max DD > 15% (unacceptable)
        # H₁: Max DD ≤ 15% (acceptable)

        threshold = 0.15  # 15% max drawdown threshold
        test_stat = observed_max_dd
        p_value = 1.0 if observed_max_dd <= threshold else 0.0  # Binary result

        return HypothesisTestResult(
            test_name="Maximum Drawdown Validation",
            null_hypothesis="Max drawdown > 15%",
            alternative_hypothesis="Max drawdown ≤ 15%",
            test_statistic=test_stat,
            p_value=p_value,
            significance_level=self.alpha,
            reject_null=observed_max_dd <= threshold,
            effect_size=observed_max_dd,
            confidence_interval=(observed_max_dd, observed_max_dd),  # Point estimate
            sample_size=len(returns),
            power=None
        )

    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe ratio"""
        if len(returns) <= 1:
            return 0.0

        # Annualize returns and volatility (assuming daily data)
        mean_return = np.mean(returns)
        volatility = np.std(returns)

        if volatility == 0:
            return float('inf') if mean_return > 0 else float('-inf')

        # Annualize
        annualized_return = mean_return * 252
        annualized_vol = volatility * np.sqrt(252)
        annualized_rf = risk_free_rate

        return (annualized_return - annualized_rf) / annualized_vol

    def _calculate_max_drawdown_from_returns(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns array"""
        if len(returns) == 0:
            return 0.0

        # Convert returns to equity curve
        equity = np.cumprod(1 + returns)

        # Calculate drawdowns
        peak = equity[0]
        max_dd = 0.0

        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd

    def _assess_overall_confidence(self,
                                 win_rate_test: HypothesisTestResult,
                                 sharpe_test: Optional[HypothesisTestResult],
                                 max_dd_test: Optional[HypothesisTestResult],
                                 sample_size: int) -> str:
        """Assess overall confidence in strategy performance"""

        if sample_size < 30:
            return "Insufficient"

        confidence_score = 0

        # Win rate test (most important)
        if win_rate_test.reject_null:
            confidence_score += 3
        elif win_rate_test.p_value < 0.1:  # Marginally significant
            confidence_score += 1

        # Sharpe ratio test
        if sharpe_test and sharpe_test.reject_null:
            confidence_score += 2

        # Max drawdown test
        if max_dd_test and max_dd_test.reject_null:
            confidence_score += 1

        # Sample size bonus
        if sample_size >= 100:
            confidence_score += 1

        if confidence_score >= 5:
            return "High"
        elif confidence_score >= 3:
            return "Medium"
        else:
            return "Low"

    def _generate_recommendations(self,
                                win_rate_test: HypothesisTestResult,
                                sharpe_test: Optional[HypothesisTestResult],
                                max_dd_test: Optional[HypothesisTestResult],
                                sample_size: int) -> List[str]:
        """Generate recommendations based on test results"""

        recommendations = []

        if sample_size < 50:
            recommendations.append(f"Sample size ({sample_size}) is small. Collect more trade data for reliable statistical tests.")

        if not win_rate_test.reject_null:
            if win_rate_test.p_value > 0.2:
                recommendations.append("Win rate improvement is not statistically significant. Consider revising strategy parameters.")
            else:
                recommendations.append("Win rate shows marginal improvement. More data needed for conclusive results.")

        if win_rate_test.reject_null:
            recommendations.append(f"✅ Win rate improvement is statistically significant (p = {win_rate_test.p_value:.3f})")

        if sharpe_test and not sharpe_test.reject_null:
            recommendations.append("Sharpe ratio is not statistically significant. Focus on risk-adjusted returns.")

        if max_dd_test and not max_dd_test.reject_null:
            recommendations.append(f"Maximum drawdown ({max_dd_test.test_statistic:.1%}) exceeds acceptable limits. Strengthen risk management.")

        if win_rate_test.reject_null and (not sharpe_test or sharpe_test.reject_null):
            recommendations.append("✅ Strategy shows promising risk-adjusted performance. Ready for further validation.")

        return recommendations

    def _calculate_statistical_power(self, sample_size: int, observed_win_rate: float) -> float:
        """Calculate statistical power of the win rate test"""

        if not HAS_STATSMODELS:
            # Simple approximation without statsmodels
            effect_size = abs(observed_win_rate - self.baseline_win_rate)
            # Rough power calculation: higher effect size and sample size = higher power
            base_power = min(0.9, effect_size * 10)  # Effect size contribution
            sample_bonus = min(0.1, sample_size / 1000)  # Sample size contribution
            return min(1.0, base_power + sample_bonus)

        try:
            effect_size = abs(observed_win_rate - self.baseline_win_rate) / np.sqrt(
                (self.baseline_win_rate * (1 - self.baseline_win_rate) +
                 observed_win_rate * (1 - observed_win_rate)) / 2
            )

            analysis = TTestPower()
            power = analysis.solve_power(
                effect_size=effect_size,
                nobs=sample_size,
                alpha=self.alpha,
                alternative='larger'
            )

            return min(1.0, power)
        except:
            return 0.5

    def _assess_sample_size(self, sample_size: int, observed_win_rate: float) -> str:
        """Assess if sample size is sufficient for reliable results"""

        min_required = 100  # Minimum for reliable statistical tests

        if sample_size >= min_required:
            return "Sufficient"
        elif sample_size >= 50:
            return "Marginal"
        else:
            return "Insufficient"

    def _create_insufficient_data_report(self, sample_size: int) -> StatisticalValidationReport:
        """Create report for insufficient data scenarios"""

        dummy_test = HypothesisTestResult(
            test_name="Insufficient Data",
            null_hypothesis="Cannot test",
            alternative_hypothesis="Cannot test",
            test_statistic=0,
            p_value=1.0,
            significance_level=self.alpha,
            reject_null=False,
            effect_size=None,
            confidence_interval=(0, 0),
            sample_size=sample_size,
            power=None
        )

        return StatisticalValidationReport(
            win_rate_test=dummy_test,
            sharpe_ratio_test=None,
            max_drawdown_test=None,
            overall_confidence="Insufficient",
            recommendations=[f"Need at least 30 trades for statistical testing. Currently have {sample_size}."],
            statistical_power=0.0,
            sample_size_assessment="Insufficient",
            generated_at=datetime.now()
        )

    def bootstrap_confidence_intervals(self,
                                     trade_results: List[Dict[str, Any]],
                                     n_bootstraps: int = 1000,
                                     confidence_level: float = 0.95) -> Dict[str, Tuple[float, float]]:
        """
        Calculate bootstrap confidence intervals for performance metrics.

        Args:
            trade_results: List of trade results
            n_bootstraps: Number of bootstrap samples
            confidence_level: Confidence level for intervals

        Returns:
            Dictionary of metric names to confidence intervals
        """

        if len(trade_results) < 10:
            return {}

        outcomes = np.array([1 if t.get('status') == 'won' else 0 for t in trade_results])

        # Bootstrap win rates
        win_rates = []
        for _ in range(n_bootstraps):
            sample = np.random.choice(outcomes, size=len(outcomes), replace=True)
            win_rates.append(np.mean(sample))

        win_rate_ci = self._calculate_bootstrap_ci(win_rates, confidence_level)

        return {
            'win_rate': win_rate_ci
        }

    def _calculate_bootstrap_ci(self, bootstrap_samples: List[float], confidence_level: float) -> Tuple[float, float]:
        """Calculate confidence interval from bootstrap samples"""
        lower_percentile = (1 - confidence_level) / 2 * 100
        upper_percentile = (1 + confidence_level) / 2 * 100

        return (
            np.percentile(bootstrap_samples, lower_percentile),
            np.percentile(bootstrap_samples, upper_percentile)
        )

    def save_validation_report(self, report: StatisticalValidationReport, filepath: str):
        """Save validation report to JSON file"""

        # Convert dataclasses to dictionaries
        report_dict = {
            'win_rate_test': {
                'test_name': report.win_rate_test.test_name,
                'null_hypothesis': report.win_rate_test.null_hypothesis,
                'alternative_hypothesis': report.win_rate_test.alternative_hypothesis,
                'test_statistic': report.win_rate_test.test_statistic,
                'p_value': report.win_rate_test.p_value,
                'significance_level': report.win_rate_test.significance_level,
                'reject_null': report.win_rate_test.reject_null,
                'effect_size': report.win_rate_test.effect_size,
                'confidence_interval': report.win_rate_test.confidence_interval,
                'sample_size': report.win_rate_test.sample_size,
                'power': report.win_rate_test.power
            },
            'overall_confidence': report.overall_confidence,
            'recommendations': report.recommendations,
            'statistical_power': report.statistical_power,
            'sample_size_assessment': report.sample_size_assessment,
            'generated_at': report.generated_at.isoformat()
        }

        if report.sharpe_ratio_test:
            report_dict['sharpe_ratio_test'] = {
                'test_name': report.sharpe_ratio_test.test_name,
                'null_hypothesis': report.sharpe_ratio_test.null_hypothesis,
                'alternative_hypothesis': report.sharpe_ratio_test.alternative_hypothesis,
                'test_statistic': report.sharpe_ratio_test.test_statistic,
                'p_value': report.sharpe_ratio_test.p_value,
                'significance_level': report.sharpe_ratio_test.significance_level,
                'reject_null': report.sharpe_ratio_test.reject_null,
                'effect_size': report.sharpe_ratio_test.effect_size,
                'confidence_interval': report.sharpe_ratio_test.confidence_interval,
                'sample_size': report.sharpe_ratio_test.sample_size,
                'power': report.sharpe_ratio_test.power
            }

        if report.max_drawdown_test:
            report_dict['max_drawdown_test'] = {
                'test_name': report.max_drawdown_test.test_name,
                'null_hypothesis': report.max_drawdown_test.null_hypothesis,
                'alternative_hypothesis': report.max_drawdown_test.alternative_hypothesis,
                'test_statistic': report.max_drawdown_test.test_statistic,
                'p_value': report.max_drawdown_test.p_value,
                'significance_level': report.max_drawdown_test.significance_level,
                'reject_null': report.max_drawdown_test.reject_null,
                'effect_size': report.max_drawdown_test.effect_size,
                'confidence_interval': report.max_drawdown_test.confidence_interval,
                'sample_size': report.max_drawdown_test.sample_size,
                'power': report.max_drawdown_test.power
            }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)