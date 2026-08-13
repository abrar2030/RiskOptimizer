"""
Risk schema for request validation.
Provides validation functions for risk calculation API requests.
"""

from typing import Any, Dict, List

from src.core.exceptions import ValidationError


def validate_returns_data(returns: Any, field_name: str = "returns") -> List[float]:
    """
    Validate returns data.

    Args:
        returns: Returns data to validate
        field_name: Name of the field for error messages

    Returns:
        Validated returns list

    Raises:
        ValidationError: If validation fails
    """
    if not returns:
        raise ValidationError(f"{field_name} data is required", field_name)

    if not isinstance(returns, list):
        raise ValidationError(f"{field_name} must be a list", field_name, returns)

    if len(returns) < 2:
        raise ValidationError(
            f"At least two data points are required in {field_name}",
            field_name,
            returns,
        )

    # Validate each return value
    for i, value in enumerate(returns):
        if not isinstance(value, (int, float)):
            raise ValidationError(
                f"Return at index {i} is not a number: {value}", field_name, value
            )

    return returns


def validate_confidence_level(confidence: object) -> float:
    """
    Validate confidence level.

    Args:
        confidence: Confidence level to validate

    Returns:
        Validated confidence level

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(confidence, (int, float)):
        raise ValidationError(
            "Confidence level must be a number", "confidence", confidence
        )

    if confidence <= 0 or confidence >= 1:
        raise ValidationError(
            "Confidence level must be between 0 and 1 (exclusive)",
            "confidence",
            confidence,
        )

    return float(confidence)


def validate_risk_free_rate(risk_free_rate: float) -> float:
    """
    Validate risk-free rate.

    Args:
        risk_free_rate: Risk-free rate to validate

    Returns:
        Validated risk-free rate

    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(risk_free_rate, (int, float)):
        raise ValidationError(
            "Risk-free rate must be a number", "risk_free_rate", risk_free_rate
        )

    return float(risk_free_rate)


def validate_var_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate VaR calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns
    returns = validate_returns_data(data["returns"])

    # Validate optional confidence level
    confidence = 0.95
    if "confidence" in data:
        confidence = validate_confidence_level(data["confidence"])

    return {"returns": returns, "confidence": confidence}


def validate_cvar_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate CVaR calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns
    returns = validate_returns_data(data["returns"])

    # Validate optional confidence level
    confidence = 0.95
    if "confidence" in data:
        confidence = validate_confidence_level(data["confidence"])

    return {"returns": returns, "confidence": confidence}


def validate_sharpe_ratio_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate Sharpe ratio calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns
    returns = validate_returns_data(data["returns"])

    # Validate optional risk-free rate
    risk_free_rate = 0.0
    if "risk_free_rate" in data:
        risk_free_rate = validate_risk_free_rate(data["risk_free_rate"])

    return {"returns": returns, "risk_free_rate": risk_free_rate}


def validate_max_drawdown_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate maximum drawdown calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns
    returns = validate_returns_data(data["returns"])

    return {"returns": returns}


def validate_risk_metrics_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate risk metrics calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns
    returns = validate_returns_data(data["returns"])

    # Validate optional confidence level
    confidence = 0.95
    if "confidence" in data:
        confidence = validate_confidence_level(data["confidence"])

    # Validate optional risk-free rate
    risk_free_rate = 0.0
    if "risk_free_rate" in data:
        risk_free_rate = validate_risk_free_rate(data["risk_free_rate"])

    return {
        "returns": returns,
        "confidence": confidence,
        "risk_free_rate": risk_free_rate,
    }


def validate_efficient_frontier_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate efficient frontier calculation request data.

    Args:
        data: Request data

    Returns:
        Validated data

    Raises:
        ValidationError: If validation fails
    """
    # Check required fields
    if "returns" not in data:
        raise ValidationError("Returns data is required", "returns")

    # Validate returns dictionary
    returns = data["returns"]
    if not isinstance(returns, dict):
        raise ValidationError(
            "Returns must be a dictionary mapping asset symbols to returns",
            "returns",
            returns,
        )

    if len(returns) < 2:
        raise ValidationError("At least two assets are required", "returns", returns)

    # Validate each asset's returns
    for asset, asset_returns in returns.items():
        if not isinstance(asset, str) or not asset.strip():
            raise ValidationError(f"Invalid asset symbol: {asset}", "returns", asset)

        validate_returns_data(asset_returns, f"returns for {asset}")

    # Validate optional min_weight
    min_weight = 0.0
    if "min_weight" in data:
        min_weight = data["min_weight"]
        if not isinstance(min_weight, (int, float)):
            raise ValidationError(
                "Minimum weight must be a number", "min_weight", min_weight
            )

        if min_weight < 0 or min_weight > 1:
            raise ValidationError(
                "Minimum weight must be between 0 and 1", "min_weight", min_weight
            )

    # Validate optional max_weight
    max_weight = 1.0
    if "max_weight" in data:
        max_weight = data["max_weight"]
        if not isinstance(max_weight, (int, float)):
            raise ValidationError(
                "Maximum weight must be a number", "max_weight", max_weight
            )

        if max_weight < 0 or max_weight > 1:
            raise ValidationError(
                "Maximum weight must be between 0 and 1", "max_weight", max_weight
            )

    # Check weight constraints
    if min_weight > max_weight:
        raise ValidationError(
            "Minimum weight cannot be greater than maximum weight",
            "min_weight",
            min_weight,
        )

    # Validate optional risk-free rate
    risk_free_rate = 0.0
    if "risk_free_rate" in data:
        risk_free_rate = validate_risk_free_rate(data["risk_free_rate"])

    # Validate optional points
    points = 20
    if "points" in data:
        points = data["points"]
        if not isinstance(points, int):
            raise ValidationError(
                "Number of points must be an integer", "points", points
            )

        if points < 2:
            raise ValidationError(
                "Number of points must be at least 2", "points", points
            )

        if points > 100:
            raise ValidationError(
                "Number of points cannot exceed 100", "points", points
            )

    return {
        "returns": returns,
        "min_weight": min_weight,
        "max_weight": max_weight,
        "risk_free_rate": risk_free_rate,
        "points": points,
    }
