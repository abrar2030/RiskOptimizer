"""
Machine Learning Risk Models for RiskOptimizer

This module provides advanced machine learning approaches for risk modeling, including:
1. Direct ML-based VaR and ES prediction
2. Copula-based dependency modeling with ML components
3. Feature engineering for risk factor analysis
4. Hybrid models combining traditional and ML approaches
"""

import logging
import os
import warnings
from typing import Union

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ml_risk_models")
warnings.filterwarnings("ignore")


class MLRiskModel:
    """Machine Learning Risk Model for VaR and ES prediction"""

    def __init__(self, model_type: str = "gbm", quantile: float = 0.05) -> None:
        """
        Initialize ML Risk Model

        Args:
            model_type: Type of ML model ('gbm', 'rf', 'nn')
            quantile: Quantile for VaR prediction (default: 0.05 for 95% VaR)
        """
        self.model_type = model_type
        self.quantile = quantile
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = None
        self.feature_importance = None
        self.trained = False
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize the ML model based on specified type"""
        if self.model_type == "gbm":
            self.model = GradientBoostingRegressor(
                loss="quantile",
                alpha=self.quantile,
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                random_state=42,
            )
        elif self.model_type == "rf":
            self.model = RandomForestRegressor(
                n_estimators=200, max_depth=10, random_state=42
            )
        elif self.model_type == "nn":
            self.model = MLPRegressor(
                hidden_layer_sizes=(50, 25),
                activation="relu",
                solver="adam",
                alpha=0.0001,
                max_iter=500,
                random_state=42,
            )
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")

    def _create_features(
        self, returns: Union[np.ndarray, pd.Series, list], feature_window: int = 10
    ) -> pd.DataFrame:
        """
        Create features from return series

        Args:
            returns: DataFrame or Series of returns
            feature_window: Window size for feature creation

        Returns:
            X: Feature matrix
            feature_names: List of feature names
        """
        if isinstance(returns, pd.Series):
            returns = pd.DataFrame(returns)
        n_samples = len(returns) - feature_window
        n_assets = len(returns.columns)
        n_extra_features = 3 if n_assets > 1 else 0
        X = np.zeros((n_samples, n_assets * 5 + n_extra_features))
        feature_names = []
        for i, col in enumerate(returns.columns):
            asset_returns = returns[col].values
            for j in range(n_samples):
                window = asset_returns[j : j + feature_window]
                X[j, i * 5] = np.mean(window)
                X[j, i * 5 + 1] = np.std(window)
                X[j, i * 5 + 2] = stats.skew(window)
                X[j, i * 5 + 3] = stats.kurtosis(window)
                X[j, i * 5 + 4] = np.min(window) / np.std(window)
            feature_names.extend(
                [
                    f"{col}_mean",
                    f"{col}_std",
                    f"{col}_skew",
                    f"{col}_kurt",
                    f"{col}_norm_min",
                ]
            )
        if n_assets > 1:
            market_returns = returns.mean(axis=1).values
            for j in range(n_samples):
                window = market_returns[j : j + feature_window]
                X[j, -3] = np.mean(window)
                X[j, -2] = np.std(window)
                X[j, -1] = np.min(window) / np.std(window)
            feature_names.extend(["market_mean", "market_std", "market_norm_min"])
        return (X, feature_names)

    def _create_targets(
        self,
        returns: Union[np.ndarray, pd.Series, list],
        feature_window: int = 10,
        horizon: int = 1,
    ) -> np.ndarray:
        """
        Create target values for training

        Args:
            returns: DataFrame or Series of returns
            feature_window: Window size for feature creation
            horizon: Forecast horizon

        Returns:
            y: Target values
        """
        if isinstance(returns, pd.Series):
            returns = pd.DataFrame(returns)
        n_samples = len(returns) - feature_window
        if len(returns.columns) > 1:
            portfolio_returns = returns.mean(axis=1).values
        else:
            portfolio_returns = returns.iloc[:, 0].values
        y = np.zeros(n_samples)
        for j in range(n_samples):
            future_window = portfolio_returns[
                j + feature_window : j + feature_window + horizon
            ]
            if len(future_window) > 0:
                y[j] = np.min(future_window)
            else:
                y[j] = portfolio_returns[j + feature_window - 1]
        y = -y
        return y

    def fit(
        self,
        returns: "np.ndarray | pd.DataFrame | list",
        feature_window: int = 10,
        horizon: int = 1,
        test_size: object = 0.2,
    ) -> "MLRiskModel":
        """
        Fit the ML model to return data

        Args:
            returns: DataFrame or Series of returns
            feature_window: Window size for feature creation
            horizon: Forecast horizon
            test_size: Proportion of data to use for testing

        Returns:
            self: The fitted model
        """
        X, self.feature_names = self._create_features(returns, feature_window)
        y = self._create_targets(returns, feature_window, horizon)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, shuffle=False
        )
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)
        self.model.fit(X_train, y_train)
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance = pd.DataFrame(
                {
                    "feature": self.feature_names,
                    "importance": self.model.feature_importances_,
                }
            ).sort_values("importance", ascending=False)
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        logger.info(
            f"Model trained - Train R²: {train_score:.4f}, Test R²: {test_score:.4f}"
        )
        self.trained = True
        return self

    def predict_var(
        self,
        returns: "np.ndarray | pd.DataFrame | list",
        confidence: float = 0.95,
        feature_window: int = 10,
    ) -> float:
        """
        Predict Value at Risk (VaR)

        Args:
            returns: DataFrame or Series of returns
            confidence: Confidence level (default: 0.95 for 95% VaR)
            feature_window: Window size for feature creation

        Returns:
            var_pred: Predicted VaR values
        """
        if not self.trained:
            raise ValueError("Model must be trained before prediction")
        X, _ = self._create_features(returns, feature_window)
        X = self.scaler.transform(X)
        var_pred = self.model.predict(X)
        if abs(1 - confidence - self.quantile) > 1e-06:
            target_quantile = 1 - confidence
            scale_factor = target_quantile / self.quantile
            var_pred = var_pred * scale_factor
        var_pred = np.maximum(var_pred, 0.001)
        return var_pred

    def predict_es(
        self,
        returns: "np.ndarray | pd.DataFrame | list",
        confidence: float = 0.95,
        feature_window: int = 10,
        n_samples: object = 1000,
    ) -> float:
        """
        Predict Expected Shortfall (ES)

        Args:
            returns: DataFrame or Series of returns
            confidence: Confidence level (default: 0.95 for 95% ES)
            feature_window: Window size for feature creation
            n_samples: Number of samples for ES estimation

        Returns:
            es_pred: Predicted ES values
        """
        if not self.trained:
            raise ValueError("Model must be trained before prediction")
        var_pred = self.predict_var(returns, confidence, feature_window)
        X, _ = self._create_features(returns, feature_window)
        X = self.scaler.transform(X)
        es_pred = np.zeros_like(var_pred)
        for i in range(len(var_pred)):
            if self.model_type == "gbm":
                quantiles = np.linspace(1 - confidence, 0.01, 10)
                tail_samples = np.zeros(len(quantiles))
                original_alpha = self.model.alpha
                for j, q in enumerate(quantiles):
                    self.model.set_params(alpha=q)
                    tail_samples[j] = self.model.predict([X[i]])[0]
                self.model.set_params(alpha=original_alpha)
                es_pred[i] = np.mean(tail_samples)
            else:
                es_pred[i] = var_pred[i] * 1.25
        es_pred = np.maximum(es_pred, var_pred * 1.05)
        return es_pred

    def plot_feature_importance(self, top_n: int = 10) -> "plt.Figure":
        """
        Plot feature importance

        Args:
            top_n: Number of top features to plot

        Returns:
            fig: Matplotlib figure
        """
        if not self.trained or self.feature_importance is None:
            raise ValueError(
                "Model must be trained with a model that supports feature importance"
            )
        top_features = self.feature_importance.head(top_n)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(top_features["feature"], top_features["importance"])
        ax.set_xlabel("Importance")
        ax.set_ylabel("Feature")
        ax.set_title(f"Top {top_n} Feature Importance")
        plt.tight_layout()
        return fig

    def save_model(self, filepath: str) -> None:
        """
        Save model to file

        Args:
            filepath: Path to save the model
        """
        if not self.trained:
            raise ValueError("Model must be trained before saving")
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "feature_importance": self.feature_importance,
                "model_type": self.model_type,
                "quantile": self.quantile,
                "trained": self.trained,
            },
            filepath,
        )
        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load_model(cls, filepath: str) -> "MLRiskModel":
        """
        Load model from file

        Args:
            filepath: Path to load the model from

        Returns:
            model: Loaded model
        """
        data = joblib.load(filepath)
        model = cls(model_type=data["model_type"], quantile=data["quantile"])
        model.model = data["model"]
        model.scaler = data["scaler"]
        model.feature_names = data["feature_names"]
        model.feature_importance = data["feature_importance"]
        model.trained = data["trained"]
        logger.info(f"Model loaded from {filepath}")
        return model


class CopulaMLRiskModel:
    """Copula-based ML Risk Model for portfolio risk estimation"""

    def __init__(self, copula_type: str = "gaussian", n_scenarios: int = 10000) -> None:
        """
        Initialize Copula ML Risk Model

        Args:
            copula_type: Type of copula ('gaussian', 't', 'clayton', 'gumbel')
            n_scenarios: Number of scenarios to generate
        """
        self.copula_type = copula_type
        self.n_scenarios = n_scenarios
        self.marginals = {}
        self.correlation_matrix = None
        self.degrees_freedom = 5
        self.asset_names = None
        self.trained = False

    def _fit_marginals(self, returns: "np.ndarray | pd.DataFrame | list") -> None:
        """
        Fit marginal distributions for each asset

        Args:
            returns: DataFrame of returns

        Returns:
            marginals: Dictionary of fitted marginal distributions
        """
        marginals = {}
        for col in returns.columns:
            kde = stats.gaussian_kde(returns[col].dropna())
            marginals[col] = {
                "kde": kde,
                "mean": returns[col].mean(),
                "std": returns[col].std(),
                "skew": stats.skew(returns[col].dropna()),
                "kurt": stats.kurtosis(returns[col].dropna()),
            }
        return marginals

    def fit(self, returns: "np.ndarray | pd.DataFrame | list") -> "CopulaMLRiskModel":
        """
        Fit the copula model to return data

        Args:
            returns: DataFrame of returns

        Returns:
            self: The fitted model
        """
        self.asset_names = returns.columns.values
        self.marginals = self._fit_marginals(returns)
        self.correlation_matrix = returns.corr().values
        if self.copula_type == "t":
            kurtosis_values = [self.marginals[col]["kurt"] for col in returns.columns]
            avg_kurtosis = np.mean(kurtosis_values)
            self.degrees_freedom = max(3, min(30, int(30 / (1 + avg_kurtosis / 3))))
        self.trained = True
        logger.info(f"Copula model fitted with {self.copula_type} copula")
        return self

    def generate_scenarios(self, n_scenarios: object = None) -> pd.DataFrame:
        """
        Generate scenarios from the fitted copula model

        Args:
            n_scenarios: Number of scenarios to generate (default: use value from initialization)

        Returns:
            scenarios: DataFrame of generated scenarios
        """
        if not self.trained:
            raise ValueError("Model must be trained before generating scenarios")
        if n_scenarios is None:
            n_scenarios = self.n_scenarios
        n_assets = len(self.asset_names)
        if self.copula_type == "gaussian":
            mvn_samples = np.random.multivariate_normal(
                mean=np.zeros(n_assets), cov=self.correlation_matrix, size=n_scenarios
            )
            uniform_samples = stats.norm.cdf(mvn_samples)
        elif self.copula_type == "t":
            mvt_samples = stats.multivariate_t.rvs(
                loc=np.zeros(n_assets),
                shape=self.correlation_matrix,
                df=self.degrees_freedom,
                size=n_scenarios,
            )
            uniform_samples = stats.t.cdf(mvt_samples, df=self.degrees_freedom)
        elif self.copula_type == "clayton" or self.copula_type == "gumbel":
            adjusted_corr = np.power(self.correlation_matrix, 1.5)
            np.fill_diagonal(adjusted_corr, 1.0)
            mvn_samples = np.random.multivariate_normal(
                mean=np.zeros(n_assets), cov=adjusted_corr, size=n_scenarios
            )
            uniform_samples = stats.norm.cdf(mvn_samples)
            if self.copula_type == "clayton":
                uniform_samples = np.power(uniform_samples, 0.7)
            else:
                uniform_samples = 1 - np.power(1 - uniform_samples, 0.7)
        else:
            raise ValueError(f"Unsupported copula type: {self.copula_type}")
        scenarios = np.zeros((n_scenarios, n_assets))
        for i, asset in enumerate(self.asset_names):
            marginal = self.marginals[asset]
            u_samples = uniform_samples[:, i]
            mean = marginal["mean"]
            std = marginal["std"]
            skew = marginal["skew"]
            if abs(skew) > 0.1:
                scenarios[:, i] = self._inverse_skewed_normal(
                    u_samples, mean, std, skew
                )
            else:
                scenarios[:, i] = stats.norm.ppf(u_samples, loc=mean, scale=std)
        scenarios_df = pd.DataFrame(scenarios, columns=self.asset_names)
        return scenarios_df

    def _inverse_skewed_normal(
        self, u: object, mean: object, std: object, skew: object
    ) -> np.ndarray:
        """
        Inverse CDF of skewed normal distribution

        Args:
            u: Uniform samples
            mean: Mean of distribution
            std: Standard deviation of distribution
            skew: Skewness parameter

        Returns:
            x: Samples from skewed normal distribution
        """
        z = stats.norm.ppf(u)
        delta = skew / (1 + skew**2) ** 0.5
        alpha = delta / (1 - delta**2) ** 0.5
        x = delta * np.abs(z) + alpha * z
        x = mean + std * x
        return x

    def calculate_var(
        self, weights: "np.ndarray | pd.DataFrame | list", confidence: float = 0.95
    ) -> float:
        """
        Calculate Value at Risk (VaR) for a portfolio

        Args:
            weights: Portfolio weights (array or dict)
            confidence: Confidence level (default: 0.95 for 95% VaR)

        Returns:
            var: VaR at specified confidence level
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating VaR")
        if isinstance(weights, dict):
            weight_array = np.zeros(len(self.asset_names))
            for i, asset in enumerate(self.asset_names):
                if asset in weights:
                    weight_array[i] = weights[asset]
            weights = weight_array
        scenarios = self.generate_scenarios()
        portfolio_returns = scenarios.dot(weights)
        var = -np.percentile(portfolio_returns, 100 * (1 - confidence))
        var = max(0.001, var)
        return var

    def calculate_es(
        self, weights: "np.ndarray | pd.DataFrame | list", confidence: float = 0.95
    ) -> float:
        """
        Calculate Expected Shortfall (ES) for a portfolio

        Args:
            weights: Portfolio weights (array or dict)
            confidence: Confidence level (default: 0.95 for 95% ES)

        Returns:
            es: ES at specified confidence level
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating ES")
        if isinstance(weights, dict):
            weight_array = np.zeros(len(self.asset_names))
            for i, asset in enumerate(self.asset_names):
                if asset in weights:
                    weight_array[i] = weights[asset]
            weights = weight_array
        scenarios = self.generate_scenarios()
        portfolio_returns = scenarios.dot(weights)
        var = -np.percentile(portfolio_returns, 100 * (1 - confidence))
        es = -portfolio_returns[portfolio_returns <= -var].mean()
        es = max(var * 1.05, es)
        return es

    def calculate_risk_metrics(
        self,
        weights: "np.ndarray | pd.DataFrame | list",
        confidence_levels: object = [0.95, 0.99],
    ) -> dict:
        """
        Calculate various risk metrics for a portfolio

        Args:
            weights: Portfolio weights (array or dict)
            confidence_levels: List of confidence levels

        Returns:
            metrics: Dictionary of risk metrics
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating risk metrics")
        if isinstance(weights, dict):
            weight_array = np.zeros(len(self.asset_names))
            for i, asset in enumerate(self.asset_names):
                if asset in weights:
                    weight_array[i] = weights[asset]
            weights = weight_array
        scenarios = self.generate_scenarios()
        portfolio_returns = scenarios.dot(weights)
        mean = portfolio_returns.mean()
        std = portfolio_returns.std()
        skewness = stats.skew(portfolio_returns)
        kurtosis = stats.kurtosis(portfolio_returns)
        metrics = {"mean": mean, "std": std, "skewness": skewness, "kurtosis": kurtosis}
        for conf in confidence_levels:
            var = -np.percentile(portfolio_returns, 100 * (1 - conf))
            es = -portfolio_returns[portfolio_returns <= -var].mean()
            var = max(0.001, var)
            es = max(var * 1.05, es)
            metrics[f"var_{int(conf * 100)}"] = var
            metrics[f"es_{int(conf * 100)}"] = es
        return metrics

    def plot_return_distribution(
        self, weights: "np.ndarray | pd.DataFrame | list", n_bins: int = 50
    ) -> "plt.Figure":
        """
        Plot return distribution for a portfolio

        Args:
            weights: Portfolio weights (array or dict)
            n_bins: Number of bins for histogram

        Returns:
            fig: Matplotlib figure
        """
        if not self.trained:
            raise ValueError("Model must be trained before plotting")
        if isinstance(weights, dict):
            weight_array = np.zeros(len(self.asset_names))
            for i, asset in enumerate(self.asset_names):
                if asset in weights:
                    weight_array[i] = weights[asset]
            weights = weight_array
        scenarios = self.generate_scenarios()
        portfolio_returns = scenarios.dot(weights)
        metrics = self.calculate_risk_metrics(weights)
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(portfolio_returns, bins=n_bins, density=True, alpha=0.7)
        x = np.linspace(portfolio_returns.min(), portfolio_returns.max(), 1000)
        ax.plot(
            x,
            stats.norm.pdf(x, metrics["mean"], metrics["std"]),
            "r-",
            lw=2,
            label="Normal Distribution",
        )
        var_95 = metrics["var_95"]
        es_95 = metrics["es_95"]
        ax.axvline(
            -var_95, color="g", linestyle="--", lw=2, label=f"VaR (95%): {var_95:.4f}"
        )
        ax.axvline(
            -es_95, color="r", linestyle="--", lw=2, label=f"ES (95%): {es_95:.4f}"
        )
        ax.set_xlabel("Return")
        ax.set_ylabel("Density")
        ax.set_title("Portfolio Return Distribution")
        ax.legend()
        stats_text = f"Mean: {metrics['mean']:.4f}\nStd Dev: {metrics['std']:.4f}\nSkewness: {metrics['skewness']:.4f}\nKurtosis: {metrics['kurtosis']:.4f}"
        ax.text(
            0.02,
            0.98,
            stats_text,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )
        plt.tight_layout()
        return fig


class HybridRiskModel:
    """Hybrid Risk Model combining traditional and ML approaches"""

    def __init__(
        self, traditional_weight: float = 0.5, ml_model_type: str = "gbm"
    ) -> None:
        """
        Initialize Hybrid Risk Model

        Args:
            traditional_weight: Weight for traditional model (0-1)
            ml_model_type: Type of ML model ('gbm', 'rf', 'nn')
        """
        self.traditional_weight = traditional_weight
        self.ml_weight = 1 - traditional_weight
        self.ml_model = MLRiskModel(model_type=ml_model_type)
        self.copula_model = CopulaMLRiskModel()
        self.trained = False

    def fit(
        self,
        returns: "np.ndarray | pd.DataFrame | list",
        feature_window: int = 10,
        horizon: int = 1,
    ) -> "HybridRiskModel":
        """
        Fit the hybrid model to return data

        Args:
            returns: DataFrame of returns
            feature_window: Window size for feature creation
            horizon: Forecast horizon

        Returns:
            self: The fitted model
        """
        self.ml_model.fit(returns, feature_window, horizon)
        self.copula_model.fit(returns)
        self.trained = True
        logger.info(
            f"Hybrid model fitted with traditional weight: {self.traditional_weight}"
        )
        return self

    def calculate_var(
        self,
        returns: "np.ndarray | pd.DataFrame | list" = None,
        weights: "np.ndarray | pd.DataFrame | list" = None,
        confidence: float = 0.95,
        feature_window: int = 10,
    ) -> float:
        """
        Calculate Value at Risk (VaR) using hybrid approach

        Args:
            returns: DataFrame of returns (for ML model)
            weights: Portfolio weights (for copula model)
            confidence: Confidence level
            feature_window: Window size for feature creation

        Returns:
            var: VaR at specified confidence level
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating VaR")
        if returns is not None:
            ml_var = self.ml_model.predict_var(returns, confidence, feature_window)[-1]
        else:
            ml_var = 0
        if weights is not None:
            copula_var = self.copula_model.calculate_var(weights, confidence)
        else:
            copula_var = 0
        if returns is not None and weights is not None:
            var = self.traditional_weight * copula_var + self.ml_weight * ml_var
        elif returns is not None:
            var = ml_var
        elif weights is not None:
            var = copula_var
        else:
            raise ValueError("Either returns or weights must be provided")
        var = max(0.001, var)
        return var

    def calculate_es(
        self,
        returns: "np.ndarray | pd.DataFrame | list" = None,
        weights: "np.ndarray | pd.DataFrame | list" = None,
        confidence: float = 0.95,
        feature_window: int = 10,
    ) -> float:
        """
        Calculate Expected Shortfall (ES) using hybrid approach

        Args:
            returns: DataFrame of returns (for ML model)
            weights: Portfolio weights (for copula model)
            confidence: Confidence level
            feature_window: Window size for feature creation

        Returns:
            es: ES at specified confidence level
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating ES")
        if returns is not None:
            ml_es = self.ml_model.predict_es(returns, confidence, feature_window)[-1]
        else:
            ml_es = 0
        if weights is not None:
            copula_es = self.copula_model.calculate_es(weights, confidence)
        else:
            copula_es = 0
        if returns is not None and weights is not None:
            es = self.traditional_weight * copula_es + self.ml_weight * ml_es
        elif returns is not None:
            es = ml_es
        elif weights is not None:
            es = copula_es
        else:
            raise ValueError("Either returns or weights must be provided")
        var = self.calculate_var(returns, weights, confidence, feature_window)
        es = max(var * 1.05, es)
        return es

    def calculate_risk_metrics(
        self,
        returns: "np.ndarray | pd.DataFrame | list" = None,
        weights: "np.ndarray | pd.DataFrame | list" = None,
        confidence_levels: object = [0.95, 0.99],
        feature_window: int = 10,
    ) -> dict:
        """
        Calculate various risk metrics using hybrid approach

        Args:
            returns: DataFrame of returns (for ML model)
            weights: Portfolio weights (for copula model)
            confidence_levels: List of confidence levels
            feature_window: Window size for feature creation

        Returns:
            metrics: Dictionary of risk metrics
        """
        if not self.trained:
            raise ValueError("Model must be trained before calculating risk metrics")
        metrics = {}
        for conf in confidence_levels:
            var = self.calculate_var(returns, weights, conf, feature_window)
            es = self.calculate_es(returns, weights, conf, feature_window)
            metrics[f"var_{int(conf * 100)}"] = var
            metrics[f"es_{int(conf * 100)}"] = es
        if weights is not None:
            copula_metrics = self.copula_model.calculate_risk_metrics(
                weights, confidence_levels
            )
            for key in ["mean", "std", "skewness", "kurtosis"]:
                metrics[key] = copula_metrics[key]
        return metrics


if __name__ == "__main__":
    np.random.seed(42)
    n_days = 1000
    returns = pd.DataFrame(
        {
            "Asset_1": np.random.normal(0.001, 0.02, n_days),
            "Asset_2": np.random.normal(0.0005, 0.015, n_days),
            "Asset_3": np.random.normal(0.0008, 0.025, n_days),
        }
    )
    returns.index = pd.date_range(start="2020-01-01", periods=n_days, freq="B")
    ml_model = MLRiskModel(model_type="gbm")
    ml_model.fit(returns, feature_window=10, horizon=1)
    var_pred = ml_model.predict_var(returns, confidence=0.95)
    logger.info(f"ML VaR prediction shape: {var_pred.shape}")
    logger.info(f"Average predicted VaR: {var_pred.mean():.4f}")
    copula_model = CopulaMLRiskModel(copula_type="gaussian")
    copula_model.fit(returns)
    weights = np.array([0.4, 0.3, 0.3])
    var = copula_model.calculate_var(weights, confidence=0.95)
    logger.info(f"Copula VaR (95%): {var:.4f}")
    es = copula_model.calculate_es(weights, confidence=0.95)
    logger.info(f"Copula ES (95%): {es:.4f}")
    hybrid_model = HybridRiskModel(traditional_weight=0.7)
    hybrid_model.fit(returns)
    hybrid_var = hybrid_model.calculate_var(returns, weights, confidence=0.95)
    logger.info(f"Hybrid VaR (95%): {hybrid_var:.4f}")
    hybrid_es = hybrid_model.calculate_es(returns, weights, confidence=0.95)
    logger.info(f"Hybrid ES (95%): {hybrid_es:.4f}")
