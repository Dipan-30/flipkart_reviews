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
    forecast_horizon: int = 7,
) -> dict:
    """
    Fit a SARIMA model on train, evaluate on test, then refit on 100% of historical data
    to generate future forecast.
    """
    SARIMAX = _safe_import_sarimax()
    logger.info(f"Fitting SARIMA{order}x{seasonal_order} on {len(train)} training points")

    train_s = train.reset_index(drop=True)
    test_s = test.reset_index(drop=True)

    # 1. Evaluation model on training set
    model = SARIMAX(
        train_s,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    result = model.fit(disp=False, maxiter=200)

    fitted_values = result.fittedvalues.tolist()

    # Train metrics
    train_pred = result.fittedvalues.values.tolist()
    train_actual = train_s.values.tolist()
    train_metrics = evaluate_forecast(train_actual, train_pred)

    # Test metrics (out-of-sample evaluation on test set)
    test_pred_obj = result.get_forecast(steps=len(test_s))
    test_pred = test_pred_obj.predicted_mean.values.tolist()
    test_actual = test_s.values.tolist()
    test_metrics = evaluate_forecast(test_actual, test_pred)

    # 2. Refit on 100% of historical data (train + test) for the final future forecast
    full_data = pd.concat([train_s, test_s]).reset_index(drop=True)
    full_model = SARIMAX(
        full_data,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    full_result = full_model.fit(disp=False, maxiter=200)
    future_forecast = full_result.get_forecast(steps=forecast_horizon).predicted_mean.values.tolist()

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
    forecast_horizon: int = 7,
) -> dict:
    """
    Fit SARIMAX using the daily sentiment index as an exogenous regressor.
    Evaluates on test set, then refits on 100% of historical data for future forecast.
    """
    SARIMAX = _safe_import_sarimax()
    logger.info(
        f"Fitting SARIMAX{order}x{seasonal_order} with sentiment exog on {len(train)} points"
    )

    train_s = train.reset_index(drop=True)
    test_s = test.reset_index(drop=True)
    exog_train_s = exog_train.reset_index(drop=True)
    exog_test_s = exog_test.reset_index(drop=True)

    # Align series for training evaluation
    exog_train_arr = exog_train_s.values.reshape(-1, 1)
    exog_test_arr = exog_test_s.values.reshape(-1, 1)

    model = SARIMAX(
        train_s,
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
    train_actual = train_s.values.tolist()
    train_metrics = evaluate_forecast(train_actual, train_pred)

    # Test metrics (out-of-sample evaluation on test set)
    test_pred_obj = result.get_forecast(steps=len(test_s), exog=exog_test_arr)
    test_pred = test_pred_obj.predicted_mean.values.tolist()
    test_actual = test_s.values.tolist()
    test_metrics = evaluate_forecast(test_actual, test_pred)

    # Prepare future exogenous values
    if future_exog is None:
        mean_exog = float(np.mean(exog_train_arr))
        future_exog_arr = np.full((forecast_horizon, 1), mean_exog)
    else:
        future_exog_arr = future_exog.values.reshape(-1, 1)

    # Refit on 100% of historical data (train + test) for final future forecast
    full_data = pd.concat([train_s, test_s]).reset_index(drop=True)
    full_exog = pd.concat([exog_train_s, exog_test_s]).reset_index(drop=True)
    full_exog_arr = full_exog.values.reshape(-1, 1)

    full_model = SARIMAX(
        full_data,
        exog=full_exog_arr,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    full_result = full_model.fit(disp=False, maxiter=200)
    future_obj = full_result.get_forecast(steps=forecast_horizon, exog=future_exog_arr)
    future_forecast = future_obj.predicted_mean.values.tolist()

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
