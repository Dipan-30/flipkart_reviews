"""
Forecast evaluation metrics: MAE, RMSE, MAPE (with safe division).
"""
import math
from typing import Sequence


def mae(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Mean Absolute Error."""
    if not actual:
        return float("nan")
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def rmse(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """Root Mean Squared Error."""
    if not actual:
        return float("nan")
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))


def mape(actual: Sequence[float], predicted: Sequence[float]) -> float:
    """
    Mean Absolute Percentage Error (in %).
    Skips pairs where actual == 0 to avoid division by zero.
    Returns nan if no valid pairs remain.
    """
    errors = [
        abs((a - p) / a) * 100
        for a, p in zip(actual, predicted)
        if a != 0
    ]
    if not errors:
        return float("nan")
    return sum(errors) / len(errors)


def evaluate_forecast(actual: Sequence[float], predicted: Sequence[float]) -> dict:
    """Return dict with MAE, RMSE, MAPE (all rounded to 4 dp)."""
    def _r(v: float) -> float | None:
        return None if math.isnan(v) else round(v, 4)

    return {
        "mae": _r(mae(actual, predicted)),
        "rmse": _r(rmse(actual, predicted)),
        "mape": _r(mape(actual, predicted)),
        "n_test_samples": len(actual),
    }
