"""
SARIMA (baseline) and SARIMAX (with sentiment exogenous variable) wrappers.

Both return a dict with:
    - model_name  : str
    - order       : (p, d, q)
    - seasonal_order : (P, D, Q, s)
    - train_metrics : {mae, rmse, mape, n_test_samples}
    - test_metrics  : {mae, rmse, mape, n_test_samples}
    - forecast      : list[float]  (future predictions)
    - fitted_values : list[float]  (in-sample fitted values on training set)
"""
import logging
import warnings
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from app.forecasting.evaluation import evaluate_forecast

logger = logging.getLogger(__name__)

# Suppress statsmodels convergence warnings for a cleaner experience
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


def _safe_import_sarimax():
    """Lazy import to surface a clear error if statsmodels is missing."""
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX  # noqa
        return SARIMAX
    except ImportError as exc:
        raise ImportError(
            "statsmodels is required for forecasting. "
            "Install it with: pip install statsmodels>=0.14.0"
        ) from exc


def fit_sarima(
    train: pd.Series,
    test: pd.Series,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0),
    forecast_horizon: int = 30,
) -> dict:
    """
    Fit a SARIMA model on train, evaluate on test, generate future forecast.
    """
    SARIMAX = _safe_import_sarimax()
    logger.info(f"Fitting SARIMA{order}x{seasonal_order} on {len(train)} training points")

    model = SARIMAX(
        train,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    result = model.fit(disp=False, maxiter=200)

    fitted_values = result.fittedvalues.tolist()

    # In-sample (train) residuals
    train_pred = result.fittedvalues.values.tolist()
    train_actual = train.values.tolist()
    train_metrics = evaluate_forecast(train_actual, train_pred)

    # Out-of-sample predictions on test set
    test_pred_obj = result.get_forecast(steps=len(test))
    test_pred = test_pred_obj.predicted_mean.values.tolist()
    test_actual = test.values.tolist()
    test_metrics = evaluate_forecast(test_actual, test_pred)

    # Future forecast
    forecast_obj = result.get_forecast(steps=len(test) + forecast_horizon)
    future_forecast = forecast_obj.predicted_mean.values[-forecast_horizon:].tolist()

    return {
        "model_name": "SARIMA",
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "test_predictions": test_pred,
        "forecast": future_forecast,
        "fitted_values": fitted_values,
    }


def fit_sarimax(
    train: pd.Series,
    test: pd.Series,
    exog_train: pd.Series,
    exog_test: pd.Series,
    future_exog: Optional[pd.Series] = None,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal_order: tuple[int, int, int, int] = (0, 0, 0, 0),
    forecast_horizon: int = 30,
) -> dict:
    """
    Fit SARIMAX using the daily sentiment index as an exogenous regressor.
    """
    SARIMAX = _safe_import_sarimax()
    logger.info(
        f"Fitting SARIMAX{order}x{seasonal_order} with sentiment exog on {len(train)} points"
    )

    # Align series
    exog_train_arr = exog_train.values.reshape(-1, 1)
    exog_test_arr = exog_test.values.reshape(-1, 1)

    model = SARIMAX(
        train,
        exog=exog_train_arr,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    result = model.fit(disp=False, maxiter=200)

    fitted_values = result.fittedvalues.tolist()

    # Train metrics
    train_pred = result.fittedvalues.values.tolist()
    train_actual = train.values.tolist()
    train_metrics = evaluate_forecast(train_actual, train_pred)

    # Test metrics
    test_pred_obj = result.get_forecast(steps=len(test), exog=exog_test_arr)
    test_pred = test_pred_obj.predicted_mean.values.tolist()
    test_actual = test.values.tolist()
    test_metrics = evaluate_forecast(test_actual, test_pred)

    # Future forecast — if no future exog provided, repeat mean of training exog
    if future_exog is None:
        mean_exog = float(np.mean(exog_train_arr))
        future_exog_arr = np.full((forecast_horizon, 1), mean_exog)
    else:
        future_exog_arr = future_exog.values.reshape(-1, 1)

    future_obj = result.get_forecast(
        steps=len(test) + forecast_horizon,
        exog=np.vstack([exog_test_arr, future_exog_arr]),
    )
    future_forecast = future_obj.predicted_mean.values[-forecast_horizon:].tolist()

    return {
        "model_name": "SARIMAX",
        "order": list(order),
        "seasonal_order": list(seasonal_order),
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "test_predictions": test_pred,
        "forecast": future_forecast,
        "fitted_values": fitted_values,
    }
