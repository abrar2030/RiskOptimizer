"""
Risk controller for handling risk calculation API endpoints.
Implements RESTful API design with proper error handling.
"""

import logging
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request
from src.api.middleware.auth_middleware import jwt_required
from src.api.schemas.risk_schema import (
    validate_cvar_request,
    validate_efficient_frontier_request,
    validate_max_drawdown_request,
    validate_risk_metrics_request,
    validate_sharpe_ratio_request,
    validate_var_request,
)
from src.core.exceptions import (
    CalculationError,
    RiskOptimizerException,
    ValidationError,
)
from src.domain.services.risk_service import risk_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create blueprint
risk_bp = Blueprint("risk", __name__, url_prefix="/api/v1/risk")


def create_success_response(
    data: Any,
    message: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create standardized success response.

    Args:
        data: Response data
        message: Optional success message
        meta: Optional metadata

    Returns:
        Standardized response dictionary
    """
    response = {"status": "success", "data": data}

    if message:
        response["message"] = message

    if meta:
        response["meta"] = meta

    return response


def create_error_response(error: RiskOptimizerException) -> Dict[str, Any]:
    """
    Create standardized error response.

    Args:
        error: Exception instance

    Returns:
        Standardized error response dictionary
    """
    return {"status": "error", "error": error.to_dict()}


@risk_bp.route("/var", methods=["POST"])
@jwt_required()
def calculate_var() -> Response:
    """
    Calculate Value at Risk (VaR) for a given set of returns.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: VaRRequest
            required:
                - returns
            properties:
                returns:
                    type: array
                    items:
                        type: number
                    description: List of historical returns.
                confidence:
                    type: number
                    format: float
                    description: Confidence level for VaR calculation (e.g., 0.95 for 95%).
                    default: 0.95
    responses:
        200:
            description: VaR calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            value_at_risk:
                                type: number
                                format: float
                                description: The calculated Value at Risk.
                    meta:
                        type: object
                        properties:
                            confidence:
                                type: number
                            data_points:
                                type: integer
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("VaR calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_var_request(data)

        # Calculate VaR
        var = risk_service.calculate_var(
            returns=validated_data["returns"],
            confidence=validated_data.get("confidence", 0.95),
        )

        # Create success response
        response = create_success_response(
            data={"value_at_risk": float(var)},
            message="VaR calculated successfully",
            meta={
                "confidence": validated_data.get("confidence", 0.95),
                "data_points": len(validated_data["returns"]),
            },
        )

        logger.info(f"VaR calculated successfully: {var}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating VaR: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(f"Calculation error for VaR: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating VaR: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error calculating VaR: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@risk_bp.route("/cvar", methods=["POST"])
@jwt_required()
def calculate_cvar() -> Response:
    """
    Calculate Conditional Value at Risk (CVaR) for a given set of returns.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: CVaRRequest
            required:
                - returns
            properties:
                returns:
                    type: array
                    items:
                        type: number
                    description: List of historical returns.
                confidence:
                    type: number
                    format: float
                    description: Confidence level for CVaR calculation (e.g., 0.95 for 95%).
                    default: 0.95
    responses:
        200:
            description: CVaR calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            conditional_value_at_risk:
                                type: number
                                format: float
                                description: The calculated Conditional Value at Risk.
                    meta:
                        type: object
                        properties:
                            confidence:
                                type: number
                            data_points:
                                type: integer
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("CVaR calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_cvar_request(data)

        # Calculate CVaR
        cvar = risk_service.calculate_cvar(
            returns=validated_data["returns"],
            confidence=validated_data.get("confidence", 0.95),
        )

        # Create success response
        response = create_success_response(
            data={"conditional_value_at_risk": float(cvar)},
            message="CVaR calculated successfully",
            meta={
                "confidence": validated_data.get("confidence", 0.95),
                "data_points": len(validated_data["returns"]),
            },
        )

        logger.info(f"CVaR calculated successfully: {cvar}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating CVaR: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(f"Calculation error for CVaR: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating CVaR: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error calculating CVaR: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@risk_bp.route("/sharpe-ratio", methods=["POST"])
@jwt_required()
def calculate_sharpe_ratio() -> Response:
    """
    Calculate Sharpe ratio for a given set of returns.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: SharpeRatioRequest
            required:
                - returns
            properties:
                returns:
                    type: array
                    items:
                        type: number
                    description: List of historical returns.
                risk_free_rate:
                    type: number
                    format: float
                    description: Risk-free rate (e.g., 0.01 for 1%).
                    default: 0.0
    responses:
        200:
            description: Sharpe ratio calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            sharpe_ratio:
                                type: number
                                format: float
                                description: The calculated Sharpe Ratio.
                    meta:
                        type: object
                        properties:
                            risk_free_rate:
                                type: number
                            data_points:
                                type: integer
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Sharpe ratio calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_sharpe_ratio_request(data)

        # Calculate Sharpe ratio
        sharpe_ratio = risk_service.calculate_sharpe_ratio(
            returns=validated_data["returns"],
            risk_free_rate=validated_data.get("risk_free_rate", 0.0),
        )

        # Create success response
        response = create_success_response(
            data={"sharpe_ratio": float(sharpe_ratio)},
            message="Sharpe ratio calculated successfully",
            meta={
                "risk_free_rate": validated_data.get("risk_free_rate", 0.0),
                "data_points": len(validated_data["returns"]),
            },
        )

        logger.info(f"Sharpe ratio calculated successfully: {sharpe_ratio}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating Sharpe ratio: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(f"Calculation error for Sharpe ratio: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating Sharpe ratio: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error calculating Sharpe ratio: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@risk_bp.route("/max-drawdown", methods=["POST"])
@jwt_required()
def calculate_max_drawdown() -> Response:
    """
    Calculate maximum drawdown for a given set of returns.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: MaxDrawdownRequest
            required:
                - returns
            properties:
                returns:
                    type: array
                    items:
                        type: number
                    description: List of historical returns.
    responses:
        200:
            description: Maximum drawdown calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            max_drawdown:
                                type: number
                                format: float
                                description: The calculated Maximum Drawdown.
                    meta:
                        type: object
                        properties:
                            data_points:
                                type: integer
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Max drawdown calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_max_drawdown_request(data)

        # Calculate max drawdown
        max_drawdown = risk_service.calculate_max_drawdown(
            returns=validated_data["returns"]
        )

        # Create success response
        response = create_success_response(
            data={"max_drawdown": float(max_drawdown)},
            message="Maximum drawdown calculated successfully",
            meta={"data_points": len(validated_data["returns"])},
        )

        logger.info(f"Maximum drawdown calculated successfully: {max_drawdown}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating max drawdown: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(f"Calculation error for max drawdown: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating max drawdown: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error calculating max drawdown: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@risk_bp.route("/portfolio-metrics", methods=["POST"])
@jwt_required()
def calculate_risk_metrics() -> Response:
    """
    Calculate comprehensive risk metrics for a portfolio.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: RiskMetricsRequest
            required:
                - returns
            properties:
                returns:
                    type: array
                    items:
                        type: number
                    description: List of historical returns for the portfolio.
                confidence:
                    type: number
                    format: float
                    description: Confidence level for VaR and CVaR calculation (e.g., 0.95 for 95%).
                    default: 0.95
                risk_free_rate:
                    type: number
                    format: float
                    description: Risk-free rate for Sharpe Ratio calculation (e.g., 0.01 for 1%).
                    default: 0.0
    responses:
        200:
            description: Risk metrics calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            expected_return:
                                type: number
                                format: float
                                description: Expected return of the portfolio.
                            volatility:
                                type: number
                                format: float
                                description: Volatility (standard deviation) of the portfolio.
                            value_at_risk:
                                type: number
                                format: float
                                description: Value at Risk (VaR) of the portfolio.
                            conditional_var:
                                type: number
                                format: float
                                description: Conditional Value at Risk (CVaR) of the portfolio.
                            sharpe_ratio:
                                type: number
                                format: float
                                description: Sharpe Ratio of the portfolio.
                            max_drawdown:
                                type: number
                                format: float
                                description: Maximum Drawdown of the portfolio.
                    meta:
                        type: object
                        properties:
                            confidence:
                                type: number
                            risk_free_rate:
                                type: number
                            data_points:
                                type: integer
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Risk metrics calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_risk_metrics_request(data)

        # Calculate risk metrics
        metrics = risk_service.calculate_portfolio_risk_metrics(
            returns=validated_data["returns"],
            confidence=validated_data.get("confidence", 0.95),
            risk_free_rate=validated_data.get("risk_free_rate", 0.0),
        )

        # Create success response — convert Decimal values to float for JSON serialization
        serializable_metrics = {
            k: float(v) if hasattr(v, "__float__") else v for k, v in metrics.items()
        }
        response = create_success_response(
            data=serializable_metrics,
            message="Risk metrics calculated successfully",
            meta={
                "confidence": validated_data.get("confidence", 0.95),
                "risk_free_rate": validated_data.get("risk_free_rate", 0.0),
                "data_points": len(validated_data["returns"]),
            },
        )

        logger.info("Risk metrics calculated successfully")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating risk metrics: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(f"Calculation error for risk metrics: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating risk metrics: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error calculating risk metrics: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@risk_bp.route("/efficient-frontier", methods=["POST"])
@jwt_required()
def calculate_efficient_frontier() -> Response:
    """
    Calculate efficient frontier for a set of assets.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: EfficientFrontierRequest
            required:
                - returns
            properties:
                returns:
                    type: object
                    additionalProperties:
                        type: array
                        items:
                            type: number
                    description: Dictionary where keys are asset names and values are lists of historical returns for each asset.
                min_weight:
                    type: number
                    format: float
                    description: Minimum weight for any asset in the portfolio.
                    default: 0.0
                max_weight:
                    type: number
                    format: float
                    description: Maximum weight for any asset in the portfolio.
                    default: 1.0
                risk_free_rate:
                    type: number
                    format: float
                    description: Risk-free rate for Sharpe Ratio calculation.
                    default: 0.0
                points:
                    type: integer
                    description: Number of points to generate on the efficient frontier.
                    default: 20
    responses:
        200:
            description: Efficient frontier calculated successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
                        properties:
                            frontier_points:
                                type: array
                                items:
                                    type: object
                                    properties:
                                        expected_return:
                                            type: number
                                            format: float
                                        volatility:
                                            type: number
                                            format: float
                                        sharpe_ratio:
                                            type: number
                                            format: float
                                        weights:
                                            type: object
                                            additionalProperties:
                                                type: number
        400:
            description: Invalid input data.
        422:
            description: Calculation error.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Efficient frontier calculation request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_efficient_frontier_request(data)

        # Calculate efficient frontier
        frontier_points = risk_service.calculate_efficient_frontier(
            returns=validated_data["returns"],
            min_weight=validated_data.get("min_weight", 0.0),
            max_weight=validated_data.get("max_weight", 1.0),
            risk_free_rate=validated_data.get("risk_free_rate", 0.0),
            points=validated_data.get("points", 20),
        )

        # Create success response — serialize Decimal values to float
        serialized_points = []
        for point in frontier_points:
            serialized_point = {}
            for k, v in point.items():
                if hasattr(v, "__float__"):
                    serialized_point[k] = float(v)
                elif isinstance(v, dict):
                    serialized_point[k] = {
                        wk: float(wv) if hasattr(wv, "__float__") else wv
                        for wk, wv in v.items()
                    }
                else:
                    serialized_point[k] = v
            serialized_points.append(serialized_point)
        response = create_success_response(
            data=serialized_points,
            message="Efficient frontier calculated successfully",
            meta={
                "assets": list(validated_data["returns"].keys()),
                "min_weight": validated_data.get("min_weight", 0.0),
                "max_weight": validated_data.get("max_weight", 1.0),
                "risk_free_rate": validated_data.get("risk_free_rate", 0.0),
                "points": len(frontier_points),
            },
        )

        logger.info(
            f"Efficient frontier calculated successfully with {len(frontier_points)} points"
        )
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error calculating efficient frontier: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except CalculationError as e:
        logger.error(
            f"Calculation error for efficient frontier: {str(e)}", exc_info=True
        )
        response = create_error_response(e)
        return jsonify(response), 422

    except RiskOptimizerException as e:
        logger.error(f"Error calculating efficient frontier: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error calculating efficient frontier: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500
