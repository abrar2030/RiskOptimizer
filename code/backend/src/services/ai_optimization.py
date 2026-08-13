"""
AI Optimization Service for RiskOptimizer Backend

Provides portfolio optimization using quantitative methods with an optional
AI/ML model layer for enhanced performance.
"""

import logging
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import minimize

# quant_ml lives at code/quant_ml, a sibling of code/backend (this file is
# code/backend/src/services/ai_optimization.py). sys.path must be extended
# *before* attempting the import below, otherwise the import always fails
# and AdvancedPortfolioOptimizer silently falls back to None even when
# quant_ml is present on disk. Four levels up from this file reaches
# code/ (matching the equivalent fix in blockchain_service.py's proxy).
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.append(_PROJECT_ROOT)

try:
    from quant_ml.ai_models.optimization_model import AdvancedPortfolioOptimizer
except ImportError:
    AdvancedPortfolioOptimizer = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(_PROJECT_ROOT, "quant_ml", "ai_models")
DEFAULT_MODEL_PATH = os.path.join(MODEL_DIR, "trained_model.joblib")


class FallbackPortfolioOptimizer:
    """Fallback optimizer using classical Markowitz mean-variance optimization."""

    def __init__(self) -> None:
        self.risk_tolerance = 5

    def optimize_portfolio(self, market_data: pd.DataFrame) -> object:
        """Optimize portfolio weights using minimum variance approach."""
        price_cols = [c for c in market_data.columns if c != "market_index"]
        prices = market_data[price_cols]
        returns = prices.pct_change().dropna()

        n = len(price_cols)
        mean_ret = returns.mean()
        cov = returns.cov()

        def neg_sharpe(w):
            port_ret = np.dot(w, mean_ret) * 252
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)) * 252)
            return -port_ret / (port_vol + 1e-8)

        constraints = [{"type": "eq", "fun": lambda x: np.sum(x) - 1}]
        bounds = [(0, 1)] * n
        x0 = np.array([1 / n] * n)
        res = minimize(
            neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=constraints
        )
        weights_arr = res.x if res.success else x0
        weights = {asset: float(w) for asset, w in zip(price_cols, weights_arr)}

        port_ret = float(np.dot(weights_arr, mean_ret) * 252)
        port_vol = float(np.sqrt(np.dot(weights_arr.T, np.dot(cov, weights_arr)) * 252))
        sharpe = port_ret / (port_vol + 1e-8)

        metrics = {
            "expected_return": port_ret,
            "volatility": port_vol,
            "sharpe_ratio": sharpe,
        }
        return weights, metrics

    def monte_carlo_simulation(
        self,
        market_data: pd.DataFrame,
        weights: "np.ndarray | pd.DataFrame | list",
        num_simulations: int = 1000,
        time_horizon: int = 252,
    ) -> object:
        """Run Monte Carlo simulation for portfolio risk assessment."""
        price_cols = [c for c in market_data.columns if c != "market_index"]
        prices = market_data[price_cols]
        returns = prices.pct_change().dropna()

        weight_arr = np.array([weights.get(c, 0) for c in price_cols])
        port_returns = returns.values @ weight_arr
        mu = float(np.mean(port_returns))
        sigma = float(np.std(port_returns))

        np.random.seed(42)
        sim_returns = np.random.normal(mu, sigma, (num_simulations, time_horizon))
        sim_paths = np.cumprod(1 + sim_returns, axis=1) * 10000
        final_values = sim_paths[:, -1]

        running_max = np.maximum.accumulate(sim_paths, axis=1)
        drawdowns = (sim_paths - running_max) / running_max
        max_dd = float(np.mean(np.min(drawdowns, axis=1)))

        simulation_df = pd.DataFrame(sim_paths.T)
        risk_metrics = {
            "expected_final_value": float(np.mean(final_values)),
            "var_95": float(np.percentile(final_values, 5)),
            "var_99": float(np.percentile(final_values, 1)),
            "max_drawdown": max_dd,
        }
        return simulation_df, risk_metrics


class AIOptimizationService:
    """Service for AI-driven portfolio optimization."""

    def __init__(self, model_path: object = None) -> None:
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.optimizer = None
        self.load_model()

    def load_model(self) -> object:
        """Load the trained model, falling back to the classical optimizer."""
        try:
            if AdvancedPortfolioOptimizer is not None and os.path.exists(
                self.model_path
            ):
                self.optimizer = AdvancedPortfolioOptimizer.load_model(self.model_path)
                logger.info(f"Loaded optimization model from {self.model_path}")
            else:
                logger.info("AI model unavailable; using fallback optimizer.")
                self.optimizer = FallbackPortfolioOptimizer()
        except Exception as e:
            logger.warning(f"Error loading AI model ({e}); using fallback optimizer.")
            self.optimizer = FallbackPortfolioOptimizer()

    def process_market_data(self, data: "np.ndarray | pd.DataFrame | list") -> object:
        """Process market data for optimization."""
        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data.copy()
        if "date" in df.columns:
            df.set_index("date", inplace=True)
        return df

    def optimize_portfolio(
        self,
        market_data: "np.ndarray | pd.DataFrame | list",
        risk_tolerance: object = 5,
    ) -> object:
        """Generate optimized portfolio allocation."""
        df = self.process_market_data(market_data)
        self.optimizer.risk_tolerance = risk_tolerance
        weights, metrics = self.optimizer.optimize_portfolio(df)
        return {
            "optimized_allocation": {k: float(v) for k, v in weights.items()},
            "performance_metrics": {
                "expected_return": float(metrics["expected_return"]),
                "volatility": float(metrics["volatility"]),
                "sharpe_ratio": float(metrics["sharpe_ratio"]),
            },
        }

    def run_risk_simulation(
        self,
        market_data: "np.ndarray | pd.DataFrame | list",
        weights: "np.ndarray | pd.DataFrame | list",
        num_simulations: object = 1000,
        time_horizon: int = 252,
    ) -> object:
        """Run Monte Carlo simulation for risk assessment."""
        df = self.process_market_data(market_data)
        simulation, risk_metrics = self.optimizer.monte_carlo_simulation(
            df, weights, num_simulations, time_horizon
        )
        percentiles = [5, 25, 50, 75, 95]
        percentile_values = np.percentile(simulation.iloc[-1], percentiles)
        return {
            "risk_metrics": {
                "expected_final_value": float(risk_metrics["expected_final_value"]),
                "value_at_risk_95": float(risk_metrics["var_95"]),
                "value_at_risk_99": float(risk_metrics["var_99"]),
                "max_drawdown": float(risk_metrics["max_drawdown"]),
            },
            "simulation_summary": {
                "initial_value": 10000,
                "time_horizon_days": time_horizon,
                "percentiles": {
                    f"p{p}": float(val)
                    for p, val in zip(percentiles, percentile_values)
                },
            },
        }

    def get_model_info(self) -> object:
        """Get information about the loaded model."""
        return {
            "model_path": self.model_path,
            "model_loaded": self.optimizer is not None,
            "model_type": type(self.optimizer).__name__ if self.optimizer else None,
        }
