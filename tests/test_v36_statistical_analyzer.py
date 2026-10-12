"""
tests/test_v36_statistical_analyzer.py - Unit & Numerical Tests for StatisticalAnalyzer
AutoDev Version 3.6 Autonomous AI Research Lab.
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import math
import unittest

from core.statistical_analyzer import (
    ANOVAResult,
    DescriptiveStatistics,
    HypothesisTestResult,
    StatisticalAnalyzer,
)


class TestStatisticalAnalyzer(unittest.TestCase):
    """Exhaustive mathematical verification of StatisticalAnalyzer routines."""

    def test_summarize_basic(self) -> None:
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = StatisticalAnalyzer.summarize(data)
        self.assertEqual(stats.count, 5)
        self.assertAlmostEqual(stats.mean, 30.0)
        self.assertAlmostEqual(stats.median, 30.0)
        self.assertAlmostEqual(stats.min_val, 10.0)
        self.assertAlmostEqual(stats.max_val, 50.0)
        self.assertAlmostEqual(stats.p25, 20.0)
        self.assertAlmostEqual(stats.p75, 40.0)
        self.assertAlmostEqual(stats.iqr, 20.0)

    def test_summarize_single_element(self) -> None:
        data = [42.0]
        stats = StatisticalAnalyzer.summarize(data)
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.mean, 42.0)
        self.assertEqual(stats.std_dev, 0.0)
        self.assertEqual(stats.variance, 0.0)

    def test_summarize_empty(self) -> None:
        stats = StatisticalAnalyzer.summarize([])
        self.assertEqual(stats.count, 0)
        self.assertEqual(stats.mean, 0.0)
        self.assertEqual(stats.std_dev, 0.0)

    def test_summarize_identical_elements(self) -> None:
        data = [7.0, 7.0, 7.0, 7.0]
        stats = StatisticalAnalyzer.summarize(data)
        self.assertEqual(stats.variance, 0.0)
        self.assertEqual(stats.std_dev, 0.0)
        self.assertEqual(stats.iqr, 0.0)

    def test_summarize_even_length(self) -> None:
        data = [1.0, 2.0, 3.0, 4.0]
        stats = StatisticalAnalyzer.summarize(data)
        self.assertEqual(stats.median, 2.5)

    def test_t_test_identical_samples(self) -> None:
        sample_a = [10.0, 10.0, 10.0, 10.0]
        sample_b = [10.0, 10.0, 10.0, 10.0]
        res = StatisticalAnalyzer.t_test_two_sample(sample_a, sample_b)
        self.assertEqual(res.test_name, "Welch's Two-Sample t-test")
        self.assertEqual(res.statistic, 0.0)
        self.assertFalse(res.is_significant)
        self.assertEqual(res.p_value, 1.0)

    def test_t_test_significant_difference(self) -> None:
        # Group 1: centered around 10; Group 2: centered around 100
        sample_a = [9.8, 10.1, 10.2, 9.9, 10.0, 10.3, 9.7]
        sample_b = [98.0, 101.5, 99.2, 100.8, 102.1, 99.5, 100.0]
        res = StatisticalAnalyzer.t_test_two_sample(sample_a, sample_b, alpha=0.01)
        self.assertTrue(res.is_significant)
        self.assertLess(res.p_value, 0.001)
        self.assertGreater(abs(res.effect_size), 5.0)

    def test_t_test_small_sample_fallback(self) -> None:
        sample_a = [1.0]
        sample_b = [2.0]
        res = StatisticalAnalyzer.t_test_two_sample(sample_a, sample_b)
        self.assertFalse(res.is_significant)
        self.assertEqual(res.p_value, 1.0)

    def test_t_test_equal_means_with_variance(self) -> None:
        sample_a = [8.0, 10.0, 12.0]
        sample_b = [9.0, 10.0, 11.0]
        res = StatisticalAnalyzer.t_test_two_sample(sample_a, sample_b)
        self.assertAlmostEqual(res.statistic, 0.0)
        self.assertFalse(res.is_significant)

    def test_mann_whitney_u_basic(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0]
        y = [5.0, 6.0, 7.0, 8.0]
        res = StatisticalAnalyzer.mann_whitney_u(x, y, alpha=0.05)
        self.assertEqual(res.test_name, "Mann-Whitney U Test")
        self.assertEqual(res.statistic, 0.0)  # Complete separation
        self.assertTrue(res.is_significant)
        self.assertLess(res.p_value, 0.05)

    def test_mann_whitney_u_tied_values(self) -> None:
        x = [2.0, 3.0, 5.0]
        y = [2.0, 4.0, 6.0]
        res = StatisticalAnalyzer.mann_whitney_u(x, y)
        self.assertIsInstance(res, HypothesisTestResult)
        self.assertGreaterEqual(res.p_value, 0.0)
        self.assertLessEqual(res.p_value, 1.0)

    def test_mann_whitney_u_empty_handling(self) -> None:
        res = StatisticalAnalyzer.mann_whitney_u([], [1.0, 2.0])
        self.assertFalse(res.is_significant)
        self.assertEqual(res.p_value, 1.0)

    def test_one_way_anova_significant(self) -> None:
        g1 = [1.0, 2.0, 1.5, 1.8]
        g2 = [10.0, 11.0, 10.5, 9.8]
        g3 = [100.0, 102.0, 101.0, 99.0]
        res = StatisticalAnalyzer.one_way_anova([g1, g2, g3], alpha=0.01)
        self.assertIsInstance(res, ANOVAResult)
        self.assertTrue(res.is_significant)
        self.assertGreater(res.f_statistic, 50.0)
        self.assertEqual(res.df_between, 2)
        self.assertEqual(res.df_within, 9)

    def test_one_way_anova_homogeneous(self) -> None:
        g1 = [5.0, 5.1, 4.9]
        g2 = [5.0, 5.2, 4.8]
        g3 = [4.9, 5.0, 5.1]
        res = StatisticalAnalyzer.one_way_anova([g1, g2, g3], alpha=0.05)
        self.assertFalse(res.is_significant)
        self.assertGreater(res.p_value, 0.05)

    def test_one_way_anova_insufficient_groups(self) -> None:
        g1 = [1.0, 2.0]
        res = StatisticalAnalyzer.one_way_anova([g1])
        self.assertFalse(res.is_significant)
        self.assertEqual(res.p_value, 1.0)

    def test_one_way_anova_zero_variance(self) -> None:
        g1 = [5.0, 5.0]
        g2 = [5.0, 5.0]
        res = StatisticalAnalyzer.one_way_anova([g1, g2])
        self.assertFalse(res.is_significant)
        self.assertEqual(res.f_statistic, 0.0)

    def test_shapiro_wilk_normality_approx(self) -> None:
        normal_like = [1.0, 2.0, 2.5, 3.0, 3.2, 3.5, 4.0, 4.5, 5.0]
        is_normal = StatisticalAnalyzer.shapiro_wilk_normality_approx(normal_like)
        self.assertTrue(is_normal)

    def test_shapiro_wilk_short_sample(self) -> None:
        short = [1.0, 2.0]
        self.assertTrue(StatisticalAnalyzer.shapiro_wilk_normality_approx(short))

    def test_shapiro_wilk_zero_variance(self) -> None:
        identical = [5.0, 5.0, 5.0]
        self.assertFalse(StatisticalAnalyzer.shapiro_wilk_normality_approx(identical))

    def test_shapiro_wilk_extreme_skew(self) -> None:
        skewed = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1000.0]
        self.assertFalse(StatisticalAnalyzer.shapiro_wilk_normality_approx(skewed))

    def test_cohens_d_interpretation(self) -> None:
        sample_a = [10.0, 11.0, 12.0]
        sample_b = [10.0, 11.0, 12.0]
        res = StatisticalAnalyzer.t_test_two_sample(sample_a, sample_b)
        self.assertAlmostEqual(res.effect_size, 0.0)

    def test_p_value_monotonicity(self) -> None:
        # Standard normal p-value calculation verification
        t_small = 1.0
        t_large = 4.0
        p_small = StatisticalAnalyzer._approx_p_value(t_small, 20.0)
        p_large = StatisticalAnalyzer._approx_p_value(t_large, 20.0)
        self.assertGreater(p_small, p_large)

    def test_to_dict_serialization(self) -> None:
        data = [1.0, 2.0, 3.0]
        stats = StatisticalAnalyzer.summarize(data)
        d = stats.to_dict()
        self.assertIn("mean", d)
        self.assertIn("std_dev", d)
        self.assertIn("median", d)

    def test_hypothesis_result_serialization(self) -> None:
        res = HypothesisTestResult(
            test_name="Sample Test",
            statistic=2.5,
            p_value=0.02,
            is_significant=True,
            effect_size=0.8,
            degrees_of_freedom=18.0,
            conclusion="Reject null hypothesis",
        )
        d = res.to_dict()
        self.assertEqual(d["statistic"], 2.5)
        self.assertTrue(d["is_significant"])

    def test_anova_serialization(self) -> None:
        anova = ANOVAResult(
            f_statistic=12.4,
            p_value=0.001,
            is_significant=True,
            df_between=2,
            df_within=27,
            eta_squared=0.48,
        )
        d = anova.to_dict()
        self.assertEqual(d["df_between"], 2)
        self.assertEqual(d["eta_squared"], 0.48)


if __name__ == "__main__":
    unittest.main()
