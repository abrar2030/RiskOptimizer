"""
Portfolio controller for handling portfolio-related API endpoints.
Implements RESTful API design with proper error handling.
"""

import logging
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request
from src.api.middleware.auth_middleware import jwt_required
from src.api.schemas.portfolio_schema import (
    validate_portfolio_request,
    validate_portfolio_update_request,
)
from src.core.exceptions import (
    BlockchainError,
    NotFoundError,
    RiskOptimizerException,
    ValidationError,
)
from src.domain.services.portfolio_service import portfolio_service
from src.utils.pagination import create_paginated_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _serialize(obj):
    """Recursively convert Decimal and non-JSON-serializable types."""
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    return obj


logger = logging.getLogger(__name__)

# Create blueprint
portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/v1/portfolios")


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


@portfolio_bp.route("/address/<user_address>", methods=["GET"])
@jwt_required()
def get_portfolio(user_address: str) -> Response:
    """
    Get portfolio by user address.
    ---
    parameters:
        - in: path
          name: user_address
          type: string
          required: true
          description: The wallet address of the user whose portfolio is to be retrieved.
    responses:
        200:
            description: Portfolio data with allocations retrieved successfully.
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
                            total_value:
                                type: string
                                description: Total value of the portfolio.
                            allocations:
                                type: array
                                items:
                                    type: object
                                    properties:
                                        asset:
                                            type: string
                                        percentage:
                                            type: string
                                        amount:
                                            type: string
                                        current_price:
                                            type: string
        400:
            description: Invalid input data.
        404:
            description: Portfolio not found for the given address.
        500:
            description: Internal server error.
    """
    try:
        logger.info(f"Get portfolio request for address: {user_address}")

        # Get portfolio from service
        portfolio_data = portfolio_service.get_portfolio_by_address(user_address)

        # Create success response
        response = create_success_response(
            data=_serialize(portfolio_data), message="Portfolio retrieved successfully"
        )

        logger.info(f"Portfolio retrieved successfully for address: {user_address}")
        return jsonify(response), 200

    except NotFoundError as e:
        logger.warning(f"Portfolio not found for address {user_address}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 404

    except ValidationError as e:
        logger.warning(f"Validation error for address {user_address}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except RiskOptimizerException as e:
        logger.error(
            f"Error getting portfolio for address {user_address}: {str(e)}",
            exc_info=True,
        )
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting portfolio for address {user_address}: {str(e)}",
            exc_info=True,
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("/address/<user_address>/onchain", methods=["GET"])
@jwt_required()
def get_onchain_portfolio(user_address: str) -> Response:
    """
    Get a user's portfolio directly from the blockchain (PortfolioTracker
    contract), independent of the database-backed portfolio returned by
    GET /address/<user_address>.
    ---
    parameters:
        - in: path
          name: user_address
          type: string
          required: true
          description: The wallet address of the user whose on-chain portfolio is to be retrieved.
    responses:
        200:
            description: On-chain portfolio data retrieved successfully.
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
                            user_address:
                                type: string
                            assets:
                                type: array
                                items:
                                    type: string
                            allocations:
                                type: array
                                items:
                                    type: number
                            version:
                                type: integer
                            updated_at:
                                type: integer
        400:
            description: Invalid address.
        404:
            description: No portfolio has been recorded on-chain for this address.
        502:
            description: Blockchain node unreachable or the call failed.
    """
    try:
        logger.info(f"Get on-chain portfolio request for address: {user_address}")

        onchain_data = portfolio_service.get_onchain_portfolio(user_address)

        response = create_success_response(
            data=onchain_data, message="On-chain portfolio retrieved successfully"
        )

        logger.info(
            f"On-chain portfolio retrieved successfully for address: {user_address}"
        )
        return jsonify(response), 200

    except NotFoundError as e:
        logger.warning(f"On-chain portfolio not found for address {user_address}")
        response = create_error_response(e)
        return jsonify(response), 404

    except ValidationError as e:
        logger.warning(f"Validation error for address {user_address}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except BlockchainError as e:
        logger.error(
            f"Blockchain error getting on-chain portfolio for address {user_address}: {str(e)}",
            exc_info=True,
        )
        response = create_error_response(e)
        return jsonify(response), 502

    except RiskOptimizerException as e:
        logger.error(
            f"Error getting on-chain portfolio for address {user_address}: {str(e)}",
            exc_info=True,
        )
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting on-chain portfolio for address {user_address}: {str(e)}",
            exc_info=True,
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("", methods=["POST"])
@jwt_required()
def create_portfolio() -> Response:
    """
    Create a new portfolio for a user.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: CreatePortfolio
            required:
                - user_id
                - user_address
                - name
            properties:
                user_id:
                    type: integer
                    description: The ID of the user creating the portfolio.
                user_address:
                    type: string
                    description: The wallet address associated with the portfolio.
                name:
                    type: string
                    description: The name of the portfolio.
                description:
                    type: string
                    description: An optional description for the portfolio.
    responses:
        201:
            description: Portfolio created successfully.
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
                            id:
                                type: integer
                            user_id:
                                type: integer
                            user_address:
                                type: string
                            name:
                                type: string
                            description:
                                type: string
                            total_value:
                                type: string
                            created_at:
                                type: string
                                format: date-time
                            updated_at:
                                type: string
                                format: date-time
        400:
            description: Invalid input data.
        401:
            description: Authentication required.
        404:
            description: User not found.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Create portfolio request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate required fields are present so a missing field returns a
        # 400 validation error rather than surfacing as a 500 from a KeyError.
        required_fields = ["user_id", "user_address", "name"]
        missing = [f for f in required_fields if data.get(f) in (None, "")]
        if missing:
            raise ValidationError(f"Missing required field(s): {', '.join(missing)}")

        validated_data = data

        # Create portfolio
        portfolio_data = portfolio_service.create_portfolio(
            user_id=validated_data["user_id"],
            user_address=validated_data["user_address"],
            name=validated_data["name"],
            description=validated_data.get("description"),
        )

        # Create success response
        response = create_success_response(
            data=_serialize(portfolio_data), message="Portfolio created successfully"
        )

        logger.info(
            f"Portfolio created successfully for user: {validated_data['user_id']}"
        )
        return jsonify(response), 201

    except ValidationError as e:
        logger.warning(f"Validation error creating portfolio: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except NotFoundError as e:
        logger.warning(f"User not found during portfolio creation: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 404

    except RiskOptimizerException as e:
        logger.error(f"Error creating portfolio: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error creating portfolio: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("/save", methods=["POST"])
@jwt_required()
def save_portfolio() -> Response:
    """
    Save portfolio allocations for a user.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: SavePortfolio
            required:
                - user_address
                - allocations
            properties:
                user_address:
                    type: string
                    description: The wallet address of the user.
                allocations:
                    type: object
                    additionalProperties:
                        type: number
                    description: Dictionary mapping asset symbols to their percentage allocations (e.g., {"BTC": 60.0, "ETH": 40.0}).
                name:
                    type: string
                    description: Optional name for the portfolio.
    responses:
        200:
            description: Portfolio allocations saved successfully.
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
                            portfolio_id:
                                type: integer
                            user_address:
                                type: string
                            name:
                                type: string
                            allocations:
                                type: object
                                additionalProperties:
                                    type: string
        400:
            description: Invalid input data.
        401:
            description: Authentication required.
        500:
            description: Internal server error.
    """
    try:
        logger.info("Save portfolio request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_portfolio_request(data)

        # Save portfolio
        portfolio_data = portfolio_service.save_portfolio_allocations(
            user_address=validated_data["user_address"],
            allocations=validated_data["allocations"],
            name=validated_data.get("name", "Default Portfolio"),
        )

        # Create success response
        response = create_success_response(
            data=_serialize(portfolio_data), message="Portfolio saved successfully"
        )

        logger.info(
            f"Portfolio saved successfully for address: {validated_data['user_address']}"
        )
        return jsonify(response), 200  # Changed to 200 as it's an update/save operation

    except ValidationError as e:
        logger.warning(f"Validation error saving portfolio: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except RiskOptimizerException as e:
        logger.error(f"Error saving portfolio: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error saving portfolio: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("/<int:portfolio_id>", methods=["PUT"])
@jwt_required()
def update_portfolio(portfolio_id: int) -> Response:
    """
    Update an existing portfolio.
    ---
    parameters:
        - in: path
          name: portfolio_id
          type: integer
          required: true
          description: The ID of the portfolio to update.
        - in: body
          name: body
          schema:
            id: UpdatePortfolio
            properties:
                name:
                    type: string
                    description: New name for the portfolio.
                description:
                    type: string
                    description: New description for the portfolio.
                total_value:
                    type: number
                    format: float
                    description: New total value for the portfolio.
    responses:
        200:
            description: Portfolio updated successfully.
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
                            id:
                                type: integer
                            user_id:
                                type: integer
                            user_address:
                                type: string
                            name:
                                type: string
                            description:
                                type: string
                            total_value:
                                type: string
                            created_at:
                                type: string
                                format: date-time
                            updated_at:
                                type: string
                                format: date-time
        400:
            description: Invalid input data.
        401:
            description: Authentication required.
        404:
            description: Portfolio not found.
        500:
            description: Internal server error.
    """
    try:
        logger.info(f"Update portfolio request for ID: {portfolio_id}")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_portfolio_update_request(data)

        # Update portfolio
        portfolio_data = portfolio_service.update_portfolio(
            portfolio_id, validated_data
        )

        # Create success response
        response = create_success_response(
            data=_serialize(portfolio_data), message="Portfolio updated successfully"
        )

        logger.info(f"Portfolio updated successfully for ID: {portfolio_id}")
        return jsonify(response), 200

    except NotFoundError as e:
        logger.warning(f"Portfolio not found for ID {portfolio_id}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 404

    except ValidationError as e:
        logger.warning(f"Validation error updating portfolio {portfolio_id}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except RiskOptimizerException as e:
        logger.error(
            f"Error updating portfolio {portfolio_id}: {str(e)}", exc_info=True
        )
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error updating portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("/<int:portfolio_id>", methods=["DELETE"])
@jwt_required()
def delete_portfolio(portfolio_id: int) -> Response:
    """
    Delete a portfolio.
    ---
    parameters:
        - in: path
          name: portfolio_id
          type: integer
          required: true
          description: The ID of the portfolio to delete.
    responses:
        204:
            description: Portfolio deleted successfully (No Content).
        401:
            description: Authentication required.
        404:
            description: Portfolio not found.
        500:
            description: Internal server error.
    """
    try:
        logger.info(f"Delete portfolio request for ID: {portfolio_id}")

        # Delete portfolio
        deleted = portfolio_service.delete_portfolio(portfolio_id)

        if not deleted:
            raise NotFoundError(
                f"Portfolio {portfolio_id} not found", "portfolio", str(portfolio_id)
            )

        # Create success response (204 No Content for successful deletion)
        return Response(status=204)  # No content for 204

    except NotFoundError as e:
        logger.warning(f"Portfolio not found for ID {portfolio_id}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 404

    except ValidationError as e:
        logger.warning(f"Validation error deleting portfolio {portfolio_id}: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except RiskOptimizerException as e:
        logger.error(
            f"Error deleting portfolio {portfolio_id}: {str(e)}", exc_info=True
        )
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error deleting portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@portfolio_bp.route("/user/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user_portfolios(user_id: int) -> Response:
    """
    Get all portfolios for a specific user.
    ---
    parameters:
        - in: path
          name: user_id
          type: integer
          required: true
          description: The ID of the user whose portfolios are to be retrieved.
    responses:
        200:
            description: List of portfolios retrieved successfully.
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: array
                        items:
                            type: object
                            properties:
                                id:
                                    type: integer
                                user_id:
                                    type: integer
                                user_address:
                                    type: string
                                name:
                                    type: string
                                description:
                                    type: string
                                total_value:
                                    type: string
                                created_at:
                                    type: string
                                    format: date-time
                                updated_at:
                                    type: string
                                    format: date-time
        400:
            description: Invalid input data.
        401:
            description: Authentication required.
        500:
            description: Internal server error.
    """
    try:
        logger.info(f"Get user portfolios request for user ID: {user_id}")

        # Get user portfolios with pagination
        portfolios = portfolio_service.get_user_portfolios(user_id)

        # Create paginated response, passing user_id so url_for can build links correctly
        response = create_paginated_response(
            portfolios,
            transform_func=lambda p: p,  # No transformation needed
            endpoint_kwargs={"user_id": user_id},
        )

        logger.info(f"Retrieved portfolios for user ID: {user_id}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(
            f"Validation error getting portfolios for user {user_id}: {str(e)}"
        )
        response = create_error_response(e)
        return jsonify(response), 400

    except RiskOptimizerException as e:
        logger.error(
            f"Error getting portfolios for user {user_id}: {str(e)}", exc_info=True
        )
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting portfolios for user {user_id}: {str(e)}",
            exc_info=True,
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500
