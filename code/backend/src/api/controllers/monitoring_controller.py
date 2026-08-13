"""
Performance monitoring controller for exposing performance metrics.
Provides endpoints for monitoring API performance and system health.
"""

from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify
from src.api.middleware.auth_middleware import admin_required
from src.core.exceptions import RiskOptimizerException
from src.core.logging import get_logger
from src.utils.cache_utils import cache_manager
from src.utils.db_utils import optimize_database_performance, query_monitor
from src.utils.performance import cache_monitor, get_performance_report, metrics

logger = get_logger(__name__)

# Create blueprint
monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/v1/monitoring")


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


@monitoring_bp.route("/performance", methods=["GET"])
@admin_required
def get_performance_metrics() -> Response:
    """
    Get comprehensive performance metrics.

    Returns:
        Performance metrics and statistics
    """
    try:
        logger.info("Performance metrics request received")

        # Get performance report
        report = get_performance_report()

        # Create success response
        response = create_success_response(
            data=report, message="Performance metrics retrieved successfully"
        )

        logger.info("Performance metrics retrieved successfully")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error getting performance metrics: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting performance metrics: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@monitoring_bp.route("/endpoints", methods=["GET"])
@admin_required
def get_endpoint_stats() -> Response:
    """
    Get endpoint performance statistics.

    Returns:
        Endpoint performance statistics
    """
    try:
        logger.info("Endpoint stats request received")

        # Get endpoint statistics
        endpoint_stats = metrics.get_all_stats()

        # Create success response
        response = create_success_response(
            data=endpoint_stats,
            message="Endpoint statistics retrieved successfully",
            meta={"count": len(endpoint_stats)},
        )

        logger.info(f"Retrieved statistics for {len(endpoint_stats)} endpoints")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error getting endpoint stats: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting endpoint stats: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@monitoring_bp.route("/system", methods=["GET"])
@admin_required
def get_system_stats() -> Response:
    """
    Get system performance statistics.

    Returns:
        System performance statistics
    """
    try:
        logger.info("System stats request received")

        # Get system statistics
        system_stats = metrics.get_system_stats()

        # Create success response
        response = create_success_response(
            data=system_stats, message="System statistics retrieved successfully"
        )

        logger.info("System statistics retrieved successfully")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error getting system stats: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error getting system stats: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@monitoring_bp.route("/cache", methods=["GET"])
@admin_required
def get_cache_stats() -> Response:
    """
    Get cache performance statistics.

    Returns:
        Cache performance statistics
    """
    try:
        logger.info("Cache stats request received")

        # Get cache statistics
        cache_stats = cache_monitor.get_stats()
        cache_health = cache_manager.get_cache_stats()

        # Combine statistics
        combined_stats = {"performance": cache_stats, "health": cache_health}

        # Create success response
        response = create_success_response(
            data=combined_stats, message="Cache statistics retrieved successfully"
        )

        logger.info("Cache statistics retrieved successfully")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error getting cache stats: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(f"Unexpected error getting cache stats: {str(e)}", exc_info=True)
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@monitoring_bp.route("/database", methods=["GET"])
@admin_required
def get_database_stats() -> Response:
    """
    Get database performance statistics.

    Returns:
        Database performance statistics
    """
    try:
        logger.info("Database stats request received")

        # Get query statistics
        query_stats = query_monitor.get_query_stats()

        # Create success response
        response = create_success_response(
            data={
                "slow_queries": query_stats,
                "threshold": query_monitor.slow_query_threshold,
            },
            message="Database statistics retrieved successfully",
            meta={"slow_query_count": len(query_stats)},
        )

        logger.info(f"Retrieved {len(query_stats)} slow query statistics")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error getting database stats: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error getting database stats: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500


@monitoring_bp.route("/optimize", methods=["POST"])
@admin_required
def optimize_performance() -> Response:
    """
    Run performance optimization.

    Returns:
        Optimization results
    """
    try:
        logger.info("Performance optimization request received")

        # Run database optimization
        db_results = optimize_database_performance()

        # Create success response
        response = create_success_response(
            data={"database_optimization": db_results},
            message="Performance optimization completed",
        )

        logger.info("Performance optimization completed successfully")
        return jsonify(response), 200

    except RiskOptimizerException as e:
        logger.error(f"Error during performance optimization: {str(e)}", exc_info=True)
        response = create_error_response(e)
        return jsonify(response), 500

    except Exception as e:
        logger.error(
            f"Unexpected error during performance optimization: {str(e)}", exc_info=True
        )
        error = RiskOptimizerException(
            f"Internal server error: {str(e)}", "INTERNAL_ERROR"
        )
        response = create_error_response(error)
        return jsonify(response), 500
