"""
core/statistical_analyzer.py - Comprehensive Scientific Statistical Analysis Engine (AutoDev Version 3.6)
Strictly 100% Python Standard Library. Zero external dependencies.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


@dataclass
class DescriptiveStatistics:
    """Complete summary of descriptive statistics for a numerical sample."""
    count: int
    mean: float
    median: float
    variance: float
    std_dev: float
    min_val: float
    max_val: float
    q25: float
    q75: float
    iqr: float
    skewness: float
    kurtosis: float
    confidence_interval_95: Tuple[float, float]

    @property
    def p25(self) -> float:
        return self.q25

    @property
    def p75(self) -> float:
        return self.q75

    def to_dict(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "mean": round(self.mean, 6),
            "median": round(self.median, 6),
            "variance": round(self.variance, 6),
            "std_dev": round(self.std_dev, 6),
            "min_val": round(self.min_val, 6),
            "max_val": round(self.max_val, 6),
            "q25": round(self.q25, 6),
            "q75": round(self.q75, 6),
            "p25": round(self.q25, 6),
            "p75": round(self.q75, 6),
            "iqr": round(self.iqr, 6),
            "skewness": round(self.skewness, 6),
            "kurtosis": round(self.kurtosis, 6),
            "confidence_interval_95": (
                round(self.confidence_interval_95[0], 6),
                round(self.confidence_interval_95[1], 6),
            ),
        }


@dataclass
class ANOVAResult:
    """Detailed result of one-way ANOVA analysis."""
    f_statistic: float
    p_value: float
    is_significant: bool
    df_between: int
    df_within: int
    eta_squared: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "f_statistic": round(self.f_statistic, 6),
            "p_value": round(self.p_value, 6),
            "is_significant": self.is_significant,
            "df_between": self.df_between,
            "df_within": self.df_within,
            "eta_squared": round(self.eta_squared, 6),
        }


@dataclass
class HypothesisTestResult:
    """Result of a statistical hypothesis test."""
    test_name: str
    statistic: float
    p_value: float
    alpha: float = 0.05
    is_significant: bool = False
    degrees_of_freedom: Optional[float] = None
    effect_size: Optional[float] = None
    interpretation: str = ""

    @property
    def conclusion(self) -> str:
        return self.interpretation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "statistic": round(self.statistic, 6),
            "p_value": round(self.p_value, 6),
            "alpha": self.alpha,
            "is_significant": self.is_significant,
            "degrees_of_freedom": round(self.degrees_of_freedom, 4) if self.degrees_of_freedom is not None else None,
            "effect_size": round(self.effect_size, 6) if self.effect_size is not None else None,
            "interpretation": self.interpretation,
            "conclusion": self.interpretation,
        }


@dataclass
class LinearRegressionResult:
    """Result of an ordinary least squares (OLS) linear regression."""
    slope: float
    intercept: float
    r_squared: float
    correlation_coefficient: float
    standard_error: float
    p_value: float

    def predict(self, x: float) -> float:
        return self.slope * x + self.intercept

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slope": round(self.slope, 6),
            "intercept": round(self.intercept, 6),
            "r_squared": round(self.r_squared, 6),
            "correlation_coefficient": round(self.correlation_coefficient, 6),
            "standard_error": round(self.standard_error, 6),
            "p_value": round(self.p_value, 6),
        }


class StatisticalAnalyzer:
    """
    Pure Python Standard Library implementation of advanced statistical methods:
    - Descriptive statistics (Mean, Median, Variance, StdDev, IQR, Skewness, Kurtosis)
    - Percentiles and Quantiles
    - Confidence Intervals (Z and Student-t based)
    - Outlier Detection (Tukey's IQR method and Z-score method)
    - Trend & Monotonicity Detection
    - Pearson & Spearman Rank Correlation
    - Ordinary Least Squares (OLS) Linear Regression
    - Two-sample Student's t-test (Welch's t-test)
    - Mann-Whitney U test (non-parametric rank sum)
    - Chi-Square test of independence
    - Bootstrap Resampling Confidence Intervals
    - Monte Carlo Simulation
    """

    # -------------------------------------------------------------------------
    # 1. Descriptive Statistics
    # -------------------------------------------------------------------------

    @staticmethod
    def mean(data: List[float]) -> float:
        if not data:
            return 0.0
        return sum(data) / len(data)

    @staticmethod
    def median(data: List[float]) -> float:
        if not data:
            return 0.0
        s = sorted(data)
        n = len(s)
        mid = n // 2
        if n % 2 == 1:
            return float(s[mid])
        return (float(s[mid - 1]) + float(s[mid])) / 2.0

    @staticmethod
    def variance(data: List[float], sample: bool = True) -> float:
        n = len(data)
        if n < 2:
            return 0.0
        m = sum(data) / n
        ss = sum((x - m) ** 2 for x in data)
        return ss / (n - 1 if sample else n)

    @staticmethod
    def std_dev(data: List[float], sample: bool = True) -> float:
        return math.sqrt(StatisticalAnalyzer.variance(data, sample=sample))

    @staticmethod
    def percentile(data: List[float], p: float) -> float:
        """Computes the p-th percentile (0.0 to 100.0) using linear interpolation."""
        if not data:
            return 0.0
        if p <= 0:
            return min(data)
        if p >= 100:
            return max(data)
        s = sorted(data)
        n = len(s)
        rank = (p / 100.0) * (n - 1)
        low_idx = int(math.floor(rank))
        high_idx = int(math.ceil(rank))
        if low_idx == high_idx:
            return float(s[low_idx])
        weight = rank - low_idx
        return (1.0 - weight) * float(s[low_idx]) + weight * float(s[high_idx])

    @staticmethod
    def summarize(data: List[float], alpha: float = 0.05) -> DescriptiveStatistics:
        """Generates comprehensive descriptive statistics for the given sample."""
        if not data:
            return DescriptiveStatistics(
                count=0, mean=0.0, median=0.0, variance=0.0, std_dev=0.0,
                min_val=0.0, max_val=0.0, q25=0.0, q75=0.0, iqr=0.0,
                skewness=0.0, kurtosis=0.0, confidence_interval_95=(0.0, 0.0)
            )

        n = len(data)
        m = StatisticalAnalyzer.mean(data)
        med = StatisticalAnalyzer.median(data)
        var = StatisticalAnalyzer.variance(data)
        sd = StatisticalAnalyzer.std_dev(data)
        min_v = min(data)
        max_v = max(data)
        q25 = StatisticalAnalyzer.percentile(data, 25.0)
        q75 = StatisticalAnalyzer.percentile(data, 75.0)
        iqr = q75 - q25

        # Sample Skewness (Fisher-Pearson standardized third moment)
        skew = 0.0
        kurt = 0.0
        if n >= 3 and sd > 1e-12:
            m3 = sum((x - m) ** 3 for x in data) / n
            m4 = sum((x - m) ** 4 for x in data) / n
            skew = (m3 / (sd ** 3)) * math.sqrt(n * (n - 1)) / (n - 2) if n > 2 else 0.0
            # Excess kurtosis
            kurt = (m4 / (sd ** 4)) - 3.0

        # Confidence Interval (Z or t approximation)
        margin = 1.96 * (sd / math.sqrt(n)) if n > 0 else 0.0
        ci = (m - margin, m + margin)

        return DescriptiveStatistics(
            count=n,
            mean=m,
            median=med,
            variance=var,
            std_dev=sd,
            min_val=min_v,
            max_val=max_v,
            q25=q25,
            q75=q75,
            iqr=iqr,
            skewness=skew,
            kurtosis=kurt,
            confidence_interval_95=ci,
        )

    # -------------------------------------------------------------------------
    # 2. Outlier Detection
    # -------------------------------------------------------------------------

    @staticmethod
    def detect_outliers_iqr(data: List[float], multiplier: float = 1.5) -> List[Tuple[int, float]]:
        """Identifies outliers using Tukey's interquartile range (IQR) method."""
        if len(data) < 4:
            return []
        q25 = StatisticalAnalyzer.percentile(data, 25.0)
        q75 = StatisticalAnalyzer.percentile(data, 75.0)
        iqr = q75 - q25
        lower_bound = q25 - (multiplier * iqr)
        upper_bound = q75 + (multiplier * iqr)
        outliers = []
        for idx, val in enumerate(data):
            if val < lower_bound or val > upper_bound:
                outliers.append((idx, val))
        return outliers

    @staticmethod
    def detect_outliers_zscore(data: List[float], threshold: float = 3.0) -> List[Tuple[int, float]]:
        """Identifies outliers using standard Z-score threshold."""
        if len(data) < 3:
            return []
        m = StatisticalAnalyzer.mean(data)
        sd = StatisticalAnalyzer.std_dev(data)
        if sd < 1e-12:
            return []
        outliers = []
        for idx, val in enumerate(data):
            z = abs((val - m) / sd)
            if z > threshold:
                outliers.append((idx, val))
        return outliers

    # -------------------------------------------------------------------------
    # 3. Correlation & Trend Analysis
    # -------------------------------------------------------------------------

    @staticmethod
    def pearson_correlation(x: List[float], y: List[float]) -> float:
        """Computes Pearson product-moment correlation coefficient r."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        n = len(x)
        mx = sum(x) / n
        my = sum(y) / n
        var_x = sum((xi - mx) ** 2 for xi in x)
        var_y = sum((yi - my) ** 2 for yi in y)
        if var_x < 1e-12 or var_y < 1e-12:
            return 0.0
        cov_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        return cov_xy / math.sqrt(var_x * var_y)

    @staticmethod
    def spearman_correlation(x: List[float], y: List[float]) -> float:
        """Computes Spearman's rank correlation coefficient rho."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        def get_ranks(seq: List[float]) -> List[float]:
            indexed = sorted(enumerate(seq), key=lambda t: t[1])
            ranks = [0.0] * len(seq)
            i = 0
            while i < len(indexed):
                j = i
                while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[j][1]:
                    j += 1
                avg_rank = (i + j + 2) / 2.0  # 1-based ranks
                for k in range(i, j + 1):
                    ranks[indexed[k][0]] = avg_rank
                i = j + 1
            return ranks

        rx = get_ranks(x)
        ry = get_ranks(y)
        return StatisticalAnalyzer.pearson_correlation(rx, ry)

    @staticmethod
    def detect_trend(data: List[float]) -> Dict[str, Any]:
        """Detects whether a series exhibits an upward, downward, or flat trend."""
        if len(data) < 2:
            return {"direction": "STATIONARY", "slope": 0.0, "strength": 0.0}
        x = list(range(len(data)))
        reg = StatisticalAnalyzer.linear_regression(x, data)
        r = reg.correlation_coefficient
        direction = "STATIONARY"
        if reg.slope > 1e-6 and reg.r_squared > 0.2:
            direction = "INCREASING"
        elif reg.slope < -1e-6 and reg.r_squared > 0.2:
            direction = "DECREASING"
        return {
            "direction": direction,
            "slope": round(reg.slope, 6),
            "r_squared": round(reg.r_squared, 6),
            "correlation": round(r, 6),
        }

    # -------------------------------------------------------------------------
    # 4. Ordinary Least Squares (OLS) Linear Regression
    # -------------------------------------------------------------------------

    @staticmethod
    def linear_regression(x: List[float], y: List[float]) -> LinearRegressionResult:
        """Fits an OLS univariate regression line: y = slope * x + intercept."""
        if len(x) != len(y) or len(x) < 2:
            return LinearRegressionResult(0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
        n = len(x)
        mx = sum(x) / n
        my = sum(y) / n
        ss_xx = sum((xi - mx) ** 2 for xi in x)
        ss_yy = sum((yi - my) ** 2 for yi in y)
        ss_xy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))

        if ss_xx < 1e-12:
            return LinearRegressionResult(0.0, my, 0.0, 0.0, 0.0, 1.0)

        slope = ss_xy / ss_xx
        intercept = my - slope * mx
        r = ss_xy / math.sqrt(ss_xx * ss_yy) if ss_yy > 1e-12 else 0.0
        r_sq = r * r

        # Residual Sum of Squares & Standard Error
        residuals = [yi - (slope * xi + intercept) for xi, yi in zip(x, y)]
        sse = sum(e * e for e in residuals)
        df = max(1, n - 2)
        mse = sse / df
        se_slope = math.sqrt(mse / ss_xx) if ss_xx > 0 else 0.0

        # p-value approximation via t-distribution
        t_stat = slope / se_slope if se_slope > 1e-12 else 0.0
        p_val = StatisticalAnalyzer._t_two_tailed_p_value(abs(t_stat), df)

        return LinearRegressionResult(
            slope=slope,
            intercept=intercept,
            r_squared=r_sq,
            correlation_coefficient=r,
            standard_error=se_slope,
            p_value=p_val,
        )

    # -------------------------------------------------------------------------
    # 5. Hypothesis Testing: Student's t-test (Welch's Two-Sample t-test)
    # -------------------------------------------------------------------------

    @staticmethod
    def t_test_two_sample(
        sample_a: List[float],
        sample_b: List[float],
        alpha: float = 0.05,
    ) -> HypothesisTestResult:
        """
        Welch's two-sample t-test for unequal variances.
        Tests H0: mean(sample_a) == mean(sample_b) vs H1: mean(sample_a) != mean(sample_b).
        """
        na = len(sample_a)
        nb = len(sample_b)
        if na < 2 or nb < 2:
            return HypothesisTestResult(
                test_name="Welch's Two-Sample t-test",
                statistic=0.0,
                p_value=1.0,
                alpha=alpha,
                is_significant=False,
                interpretation="Insufficient sample size (n < 2)",
            )

        ma = StatisticalAnalyzer.mean(sample_a)
        mb = StatisticalAnalyzer.mean(sample_b)
        va = StatisticalAnalyzer.variance(sample_a)
        vb = StatisticalAnalyzer.variance(sample_b)

        se_diff = math.sqrt((va / na) + (vb / nb))
        if se_diff < 1e-12:
            return HypothesisTestResult(
                test_name="Welch's Two-Sample t-test",
                statistic=0.0,
                p_value=1.0 if abs(ma - mb) < 1e-12 else 0.0,
                alpha=alpha,
                is_significant=abs(ma - mb) >= 1e-12,
                interpretation="Zero variance in samples",
            )

        t_stat = (ma - mb) / se_diff

        # Welch-Satterthwaite equation for degrees of freedom
        num = ((va / na) + (vb / nb)) ** 2
        denom = (((va / na) ** 2) / (na - 1)) + (((vb / nb) ** 2) / (nb - 1))
        df = num / denom if denom > 0 else float(na + nb - 2)

        p_val = StatisticalAnalyzer._t_two_tailed_p_value(abs(t_stat), df)

        # Cohen's d effect size
        s_pooled = math.sqrt(((na - 1) * va + (nb - 1) * vb) / max(1, na + nb - 2))
        cohens_d = (ma - mb) / s_pooled if s_pooled > 1e-12 else 0.0

        is_sig = p_val < alpha
        interp = (
            f"Statistically significant difference (p={p_val:.4f} < {alpha}, d={cohens_d:.2f})"
            if is_sig else
            f"No statistically significant difference (p={p_val:.4f} >= {alpha})"
        )

        return HypothesisTestResult(
            test_name="Welch's Two-Sample t-test",
            statistic=t_stat,
            p_value=p_val,
            alpha=alpha,
            is_significant=is_sig,
            degrees_of_freedom=df,
            effect_size=cohens_d,
            interpretation=interp,
        )

    # -------------------------------------------------------------------------
    # 6. Hypothesis Testing: Mann-Whitney U Test (Non-parametric)
    # -------------------------------------------------------------------------

    @staticmethod
    def mann_whitney_u(
        sample_a: List[float],
        sample_b: List[float],
        alpha: float = 0.05,
    ) -> HypothesisTestResult:
        """
        Mann-Whitney U test (Wilcoxon rank-sum test) for two independent groups.
        Tests whether one distribution is stochastically greater than the other.
        """
        na = len(sample_a)
        nb = len(sample_b)
        if na < 1 or nb < 1:
            return HypothesisTestResult(
                test_name="Mann-Whitney U Test",
                statistic=0.0,
                p_value=1.0,
                alpha=alpha,
                is_significant=False,
                interpretation="Empty sample",
            )

        combined = [(val, 'A') for val in sample_a] + [(val, 'B') for val in sample_b]
        combined.sort(key=lambda t: t[0])

        # Assign average ranks for ties
        ranks_a = 0.0
        i = 0
        while i < len(combined):
            j = i
            while j < len(combined) - 1 and combined[j + 1][0] == combined[j][0]:
                j += 1
            avg_rank = (i + j + 2) / 2.0
            for k in range(i, j + 1):
                if combined[k][1] == 'A':
                    ranks_a += avg_rank
            i = j + 1

        u1 = ranks_a - (na * (na + 1) / 2.0)
        u2 = (na * nb) - u1
        u_stat = min(u1, u2)

        # Normal approximation for large samples or fallback
        mu_u = (na * nb) / 2.0
        sigma_u = math.sqrt((na * nb * (na + nb + 1)) / 12.0)
        z = (u_stat - mu_u) / sigma_u if sigma_u > 1e-12 else 0.0
        p_val = 2.0 * (1.0 - StatisticalAnalyzer._standard_normal_cdf(abs(z)))

        # Rank-biserial correlation as effect size
        r_rb = 1.0 - (2.0 * u_stat) / (na * nb) if (na * nb) > 0 else 0.0

        is_sig = p_val < alpha
        return HypothesisTestResult(
            test_name="Mann-Whitney U Test",
            statistic=u_stat,
            p_value=p_val,
            alpha=alpha,
            is_significant=is_sig,
            effect_size=r_rb,
            interpretation=f"{'Significant' if is_sig else 'Insignificant'} difference in distributions (p={p_val:.4f})",
        )

    # -------------------------------------------------------------------------
    # 6b. Hypothesis Testing: One-Way ANOVA (Analysis of Variance)
    # -------------------------------------------------------------------------

    @staticmethod
    def one_way_anova(groups: List[List[float]], alpha: float = 0.05) -> ANOVAResult:
        """
        One-way Analysis of Variance (ANOVA) testing equality of means across k groups.
        """
        k = len(groups)
        valid_groups = [g for g in groups if len(g) > 0]
        if k < 2 or len(valid_groups) < 2:
            return ANOVAResult(
                f_statistic=0.0,
                p_value=1.0,
                is_significant=False,
                df_between=max(0, k - 1),
                df_within=0,
                eta_squared=0.0,
            )

        total_n = sum(len(g) for g in groups)
        df_between = k - 1
        df_within = total_n - k
        if df_within <= 0:
            return ANOVAResult(
                f_statistic=0.0,
                p_value=1.0,
                is_significant=False,
                df_between=df_between,
                df_within=max(1, df_within),
                eta_squared=0.0,
            )

        all_values = [x for g in groups for x in g]
        grand_mean = sum(all_values) / total_n

        ss_between = sum(len(g) * ((sum(g) / len(g)) - grand_mean) ** 2 for g in groups)
        ss_within = sum(sum((x - (sum(g) / len(g))) ** 2 for x in g) for g in groups)
        ss_total = ss_between + ss_within

        ms_between = ss_between / df_between if df_between > 0 else 0.0
        ms_within = ss_within / df_within if df_within > 0 else 0.0

        if ms_within <= 1e-12:
            f_stat = 0.0 if ms_between <= 1e-12 else 999999.0
            p_val = 1.0 if ms_between <= 1e-12 else 0.00001
        else:
            f_stat = ms_between / ms_within
            x = (df_between * f_stat) / (df_between * f_stat + df_within)
            p_val = max(0.0, min(1.0, 1.0 - StatisticalAnalyzer._incomplete_beta(x, df_between / 2.0, df_within / 2.0)))

        eta_squared = ss_between / ss_total if ss_total > 1e-12 else 0.0
        is_sig = p_val < alpha

        return ANOVAResult(
            f_statistic=f_stat,
            p_value=p_val,
            is_significant=is_sig,
            df_between=df_between,
            df_within=df_within,
            eta_squared=eta_squared,
        )

    # -------------------------------------------------------------------------
    # 6c. Normality Approximation: Shapiro-Wilk Approximation
    # -------------------------------------------------------------------------

    @staticmethod
    def shapiro_wilk_normality_approx(sample: List[float], alpha: float = 0.05) -> bool:
        """
        Evaluates sample normality via skewness and kurtosis bounds.
        Returns True if sample appears approximately normally distributed.
        """
        n = len(sample)
        if n < 3:
            return True
        v = StatisticalAnalyzer.variance(sample)
        if v < 1e-12:
            return False
        skew = StatisticalAnalyzer.skewness(sample)
        kurt = StatisticalAnalyzer.kurtosis(sample)
        return abs(skew) < 1.5 and abs(kurt) < 3.0

    @staticmethod
    def _approx_p_value(statistic: float, df: float) -> float:
        """Helper to compute two-tailed p-value given a t statistic and degrees of freedom."""
        return StatisticalAnalyzer._t_two_tailed_p_value(abs(statistic), df)

    # -------------------------------------------------------------------------
    # 7. Hypothesis Testing: Chi-Square Test of Independence
    # -------------------------------------------------------------------------

    @staticmethod
    def chi_square_test(contingency_table: List[List[float]], alpha: float = 0.05) -> HypothesisTestResult:
        """
        Pearson's chi-square test of independence for an R x C contingency table.
        """
        if not contingency_table or not contingency_table[0]:
            return HypothesisTestResult("Chi-Square", 0.0, 1.0, alpha, False, interpretation="Empty table")

        rows = len(contingency_table)
        cols = len(contingency_table[0])
        row_totals = [sum(row) for row in contingency_table]
        col_totals = [sum(contingency_table[r][c] for r in range(rows)) for c in range(cols)]
        grand_total = sum(row_totals)

        if grand_total < 1e-12:
            return HypothesisTestResult("Chi-Square", 0.0, 1.0, alpha, False, interpretation="Zero sum table")

        chi2_stat = 0.0
        for r in range(rows):
            for c in range(cols):
                expected = (row_totals[r] * col_totals[c]) / grand_total
                observed = contingency_table[r][c]
                if expected > 1e-9:
                    chi2_stat += ((observed - expected) ** 2) / expected

        df = max(1, (rows - 1) * (cols - 1))
        p_val = StatisticalAnalyzer._chi2_p_value(chi2_stat, df)
        is_sig = p_val < alpha

        # Cramér's V effect size
        min_dim = min(rows - 1, cols - 1)
        cramers_v = math.sqrt(chi2_stat / (grand_total * min_dim)) if min_dim > 0 and grand_total > 0 else 0.0

        return HypothesisTestResult(
            test_name="Chi-Square Test",
            statistic=chi2_stat,
            p_value=p_val,
            alpha=alpha,
            is_significant=is_sig,
            degrees_of_freedom=float(df),
            effect_size=cramers_v,
            interpretation=f"{'Significant' if is_sig else 'Insignificant'} association between variables (p={p_val:.4f})",
        )

    # -------------------------------------------------------------------------
    # 8. Bootstrap Sampling & Confidence Intervals
    # -------------------------------------------------------------------------

    @staticmethod
    def bootstrap_ci(
        data: List[float],
        statistic_fn: Optional[Callable[[List[float]], float]] = None,
        iterations: int = 1000,
        confidence: float = 0.95,
        seed: Optional[int] = 42,
    ) -> Tuple[float, float]:
        """
        Empirical bootstrap resampling confidence interval for an arbitrary statistic.
        """
        if not data:
            return (0.0, 0.0)
        if statistic_fn is None:
            statistic_fn = StatisticalAnalyzer.mean

        rng = random.Random(seed)
        n = len(data)
        bootstrap_stats = []

        for _ in range(iterations):
            sample = [data[rng.randint(0, n - 1)] for _ in range(n)]
            bootstrap_stats.append(statistic_fn(sample))

        bootstrap_stats.sort()
        alpha = 1.0 - confidence
        lower_idx = int(alpha / 2.0 * iterations)
        upper_idx = int((1.0 - alpha / 2.0) * iterations)
        lower_idx = max(0, min(iterations - 1, lower_idx))
        upper_idx = max(0, min(iterations - 1, upper_idx))

        return (bootstrap_stats[lower_idx], bootstrap_stats[upper_idx])

    # -------------------------------------------------------------------------
    # 9. Monte Carlo Simulation
    # -------------------------------------------------------------------------

    @staticmethod
    def monte_carlo_simulation(
        param_distributions: Dict[str, Tuple[float, float]],  # param -> (mean, std)
        evaluator_fn: Callable[[Dict[str, float]], float],
        trials: int = 2000,
        seed: Optional[int] = 42,
    ) -> Dict[str, Any]:
        """
        Executes a Monte Carlo simulation over parameterized Gaussian distributions.
        Returns quantiles, mean, variance, and confidence interval of outcomes.
        """
        rng = random.Random(seed)
        outcomes = []

        for _ in range(trials):
            params = {}
            for name, (mu, sigma) in param_distributions.items():
                params[name] = rng.gauss(mu, max(1e-9, sigma))
            outcomes.append(evaluator_fn(params))

        outcomes.sort()
        summary = StatisticalAnalyzer.summarize(outcomes)
        return {
            "trials": trials,
            "mean_outcome": summary.mean,
            "median_outcome": summary.median,
            "std_dev": summary.std_dev,
            "p05": StatisticalAnalyzer.percentile(outcomes, 5.0),
            "p25": summary.q25,
            "p75": summary.q75,
            "p95": StatisticalAnalyzer.percentile(outcomes, 95.0),
            "p99": StatisticalAnalyzer.percentile(outcomes, 99.0),
            "ci_95": summary.confidence_interval_95,
        }

    # -------------------------------------------------------------------------
    # Internal Probability Distribution Approximations (Pure Stdlib)
    # -------------------------------------------------------------------------

    @staticmethod
    def _standard_normal_cdf(x: float) -> float:
        """Standard normal cumulative distribution function (CDF) via error function."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def _t_two_tailed_p_value(t: float, df: float) -> float:
        """
        Two-tailed p-value approximation for Student's t-distribution.
        Uses Hill's polynomial approximation and normal limit for df > 30.
        """
        if df <= 0:
            return 1.0
        if df > 120:
            # Gaussian limit
            return 2.0 * (1.0 - StatisticalAnalyzer._standard_normal_cdf(abs(t)))

        # Regularized incomplete beta function approximation via transformation
        x = df / (df + t * t)
        # Symmetrical approximation
        a = df / 2.0
        b = 0.5
        # Continued fraction approximation for I_x(a, b)
        p = StatisticalAnalyzer._incomplete_beta(x, a, b)
        return max(0.0, min(1.0, p))

    @staticmethod
    def _chi2_p_value(chi2: float, df: int) -> float:
        """Right-tail p-value for chi-square distribution via regularized incomplete gamma."""
        if chi2 <= 0 or df <= 0:
            return 1.0
        # p-value = 1 - P(df/2, chi2/2) = Q(df/2, chi2/2)
        s = df / 2.0
        z = chi2 / 2.0
        return max(0.0, min(1.0, StatisticalAnalyzer._upper_gamma(s, z)))

    @staticmethod
    def _incomplete_beta(x: float, a: float, b: float) -> float:
        """Approximates regularized incomplete beta function I_x(a, b)."""
        if x <= 0:
            return 0.0
        if x >= 1.0:
            return 1.0
        # Use series or normal approximation
        # For our t-test approximation:
        log_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        factor = math.exp(a * math.log(x) + b * math.log(1.0 - x) - log_beta) / a
        # Hypergeometric series expansion
        term = 1.0
        sum_val = 1.0
        for n in range(1, 40):
            term *= ((a + n - 1) * (1.0 - b + n - 1) / (a + n)) * (x / n)
            sum_val += term
            if abs(term) < 1e-8:
                break
        return max(0.0, min(1.0, factor * sum_val))

    @staticmethod
    def _upper_gamma(s: float, z: float) -> float:
        """Approximates upper regularized incomplete gamma Q(s, z)."""
        if z <= 0:
            return 1.0
        if z < s + 1.0:
            # Series for lower gamma, then Q = 1 - P
            log_gamma = math.lgamma(s)
            sum_val = 1.0 / s
            term = 1.0 / s
            for n in range(1, 60):
                term *= z / (s + n)
                sum_val += term
                if abs(term) < 1e-9:
                    break
            p = sum_val * math.exp(s * math.log(z) - z - log_gamma)
            return max(0.0, min(1.0, 1.0 - p))
        else:
            # Continued fraction for upper gamma
            log_gamma = math.lgamma(s)
            # Lentz's method
            b0 = 0.0
            f = 1e-30
            c = f
            d = 0.0
            for i in range(1, 60):
                an = -i * (i - s) if i > 1 else 1.0
                bn = 2.0 * i - 1.0 + z - s
                d = bn + an * d
                if abs(d) < 1e-30:
                    d = 1e-30
                c = bn + an / c
                if abs(c) < 1e-30:
                    c = 1e-30
                d = 1.0 / d
                delta = c * d
                f *= delta
                if abs(delta - 1.0) < 1e-9:
                    break
            q = math.exp(s * math.log(z) - z - log_gamma) * f
            return max(0.0, min(1.0, q))
