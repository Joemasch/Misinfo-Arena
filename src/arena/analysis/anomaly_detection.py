"""
Anomaly detection for episode-level metrics.
"""

from __future__ import annotations

import pandas as pd


def compute_iqr_outliers(series: pd.Series) -> tuple[pd.Series, float, float, float, float]:
    """
    IQR-based outlier detection.
    Returns (is_outlier, lower, upper, q1, q3).
    """
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return pd.Series([False] * len(series), index=series.index), 0.0, 0.0, 0.0, 0.0

    q1 = float(clean.quantile(0.25))
    q3 = float(clean.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    vals = pd.to_numeric(series, errors="coerce")
    is_outlier = (vals < lower) | (vals > upper)
    return is_outlier.fillna(False), lower, upper, q1, q3


def compute_mad_outliers(series: pd.Series, threshold: float = 3.5) -> tuple[pd.Series, pd.Series, float, float]:
    """
    MAD (Median Absolute Deviation) based robust z-score.
    Returns (is_outlier, robust_z, median_val, mad_val).
    """
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 2:
        return pd.Series([False] * len(series), index=series.index), pd.Series([0.0] * len(series), index=series.index), 0.0, 0.0

    median_val = float(clean.median())
    mad = (clean - median_val).abs().median()
    if mad == 0 or pd.isna(mad):
        return pd.Series([False] * len(series), index=series.index), pd.Series([0.0] * len(series), index=series.index), median_val, 0.0

    vals = pd.to_numeric(series, errors="coerce")
    robust_z = 0.6745 * (vals - median_val) / mad
    is_outlier = robust_z.abs() > threshold
    return is_outlier.fillna(False), robust_z.fillna(0), median_val, float(mad)
