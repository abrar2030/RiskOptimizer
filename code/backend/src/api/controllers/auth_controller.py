"""
Authentication controller for handling user authentication API endpoints.
Implements user registration, login, token refresh, and logout.
"""

import logging
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request
from src.api.schemas.auth_schema import (
    validate_login_request,
    validate_refresh_token_request,
    validate_register_request,
)
from src.core.exceptions import (
    AuthenticationError,
    ConflictError,
    RiskOptimizerException,
    ValidationError,
)
from src.domain.services.auth_service import auth_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


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


@auth_bp.route("/register", methods=["POST"])
def register() -> Response:
    """
    Register a new user.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: UserRegister
            required:
                - email
                - username
                - password
            properties:
                email:
                    type: string
                    format: email
                    description: User's email address
                username:
                    type: string
                    description: User's chosen username
                password:
                    type: string
                    format: password
                    description: User's password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char)
                wallet_address:
                    type: string
                    description: Optional blockchain wallet address
    responses:
        201:
            description: User registered successfully
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
                            user:
                                type: object
                                properties:
                                    id:
                                        type: integer
                                    email:
                                        type: string
                                    username:
                                        type: string
                                    role:
                                        type: string
                                    is_verified:
                                        type: boolean
                                    wallet_address:
                                        type: string
                                    created_at:
                                        type: string
                                        format: date-time
                                    updated_at:
                                        type: string
                                        format: date-time
                            tokens:
                                type: object
                                properties:
                                    access_token:
                                        type: string
                                    refresh_token:
                                        type: string
                                    token_type:
                                        type: string
                                    expires_in:
                                        type: integer
        400:
            description: Invalid input data
        409:
            description: User with email or username already exists
        500:
            description: Internal server error
    """
    try:
        logger.info("User registration request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_register_request(data)

        # Register user
        user_data, tokens = auth_service.register_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
            wallet_address=validated_data.get("wallet_address"),
        )

        # Create success response
        response = create_success_response(
            data={"user": user_data, "tokens": tokens},
            message="User registered successfully",
        )

        logger.info(f"User registered successfully: {validated_data['email']}")
        return jsonify(response), 201

    except ValidationError as e:
        logger.warning(f"Validation error during registration: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except ConflictError as e:
        logger.warning(f"Conflict during registration: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 409

    except RiskOptimizerException as e:
        logger.error(f"Error during registration: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error during registration: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@auth_bp.route("/login", methods=["POST"])
def login() -> Response:
    """
    Authenticate a user and issue tokens.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: UserLogin
            required:
                - email
                - password
            properties:
                email:
                    type: string
                    format: email
                    description: User's email address
                password:
                    type: string
                    format: password
                    description: User's password
    responses:
        200:
            description: User authenticated successfully
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
                            user:
                                type: object
                                properties:
                                    id:
                                        type: integer
                                    email:
                                        type: string
                                    username:
                                        type: string
                                    role:
                                        type: string
                                    is_verified:
                                        type: boolean
                                    wallet_address:
                                        type: string
                                    created_at:
                                        type: string
                                        format: date-time
                                    updated_at:
                                        type: string
                                        format: date-time
                            tokens:
                                type: object
                                properties:
                                    access_token:
                                        type: string
                                    refresh_token:
                                        type: string
                                    token_type:
                                        type: string
                                    expires_in:
                                        type: integer
        400:
            description: Invalid input data
        401:
            description: Invalid email or password, or account locked
        500:
            description: Internal server error
    """
    try:
        logger.info("User login request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_login_request(data)

        # Authenticate user
        user_data, tokens = auth_service.authenticate_user(
            email=validated_data["email"], password=validated_data["password"]
        )

        # Create success response
        response = create_success_response(
            data={"user": user_data, "tokens": tokens},
            message="User authenticated successfully",
        )

        logger.info(f"User authenticated successfully: {validated_data['email']}")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error during login: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except AuthenticationError as e:
        logger.warning(f"Authentication error: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 401

    except RiskOptimizerException as e:
        logger.error(f"Error during login: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@auth_bp.route("/refresh", methods=["POST"])
def refresh_token() -> Response:
    """
    Refresh access token using a valid refresh token.
    ---
    parameters:
        - in: body
          name: body
          schema:
            id: RefreshTokenRequest
            required:
                - refresh_token
            properties:
                refresh_token:
                    type: string
                    description: The refresh token obtained during login
    responses:
        200:
            description: Access token refreshed successfully
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
                            access_token:
                                type: string
                            token_type:
                                type: string
                            expires_in:
                                type: integer
        400:
            description: Invalid input data
        401:
            description: Invalid or expired refresh token
        500:
            description: Internal server error
    """
    try:
        logger.info("Token refresh request received")

        # Get request data
        data = request.get_json(silent=True)
        if not data:
            raise ValidationError("Request body is required")

        # Validate request data
        validated_data = validate_refresh_token_request(data)

        # Refresh token
        tokens = auth_service.refresh_access_token(validated_data["refresh_token"])

        # Create success response
        response = create_success_response(
            data=tokens, message="Access token refreshed successfully"
        )

        logger.info("Access token refreshed successfully")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error during token refresh: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except AuthenticationError as e:
        logger.warning(f"Authentication error during token refresh: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 401

    except RiskOptimizerException as e:
        logger.error(f"Error during token refresh: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@auth_bp.route("/logout", methods=["POST"])
def logout() -> Response:
    """
    Logout a user by blacklisting their tokens.
    ---
    parameters:
        - in: header
          name: Authorization
          type: string
          required: true
          description: Bearer token (access token)
        - in: body
          name: body
          schema:
            id: LogoutRequest
            required:
                - refresh_token
            properties:
                refresh_token:
                    type: string
                    description: The refresh token to blacklist
    responses:
        200:
            description: User logged out successfully
            schema:
                type: object
                properties:
                    status:
                        type: string
                    message:
                        type: string
                    data:
                        type: object
        400:
            description: Invalid input data
        401:
            description: Missing or invalid Authorization header, or invalid tokens
        500:
            description: Internal server error
    """
    try:
        logger.info("User logout request received")

        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid Authorization header")

        # Extract access token
        access_token = auth_header.split(" ")[1]

        # Get refresh token from request body
        data = request.get_json(silent=True)
        if not data or "refresh_token" not in data:
            raise ValidationError("Refresh token is required", "refresh_token")

        refresh_token = data["refresh_token"]

        # Logout user
        auth_service.logout_user(access_token, refresh_token)

        # Create success response
        response = create_success_response(
            data={}, message="User logged out successfully"
        )

        logger.info("User logged out successfully")
        return jsonify(response), 200

    except ValidationError as e:
        logger.warning(f"Validation error during logout: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 400

    except AuthenticationError as e:
        logger.warning(f"Authentication error during logout: {str(e)}")
        response = create_error_response(e)
        return jsonify(response), 401

    except RiskOptimizerException as e:
        logger.error(f"Error during logout: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500
