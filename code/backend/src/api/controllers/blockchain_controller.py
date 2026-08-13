"""
Blockchain controller for on-chain transaction history and portfolio
integrity verification endpoints.

Distinct from portfolio_controller.py's GET /portfolios/address/<addr>/onchain
(which reads the current PortfolioTracker allocation snapshot for a wallet
address): this controller is keyed by database portfolio_id (matching
mobile-frontend's existing apiService.getTransactionHistory/
verifyPortfolioIntegrity calls, which already expected routes at this
/api/v1/blockchain/* prefix before any existed) and reads the append-only
PortfolioLedger transaction log for that portfolio's associated wallet
address.
"""

import logging

from flask import Blueprint, Response, jsonify
from src.api.controllers.portfolio_controller import create_success_response
from src.api.middleware.auth_middleware import jwt_required
from src.core.exceptions import BlockchainError, NotFoundError, RiskOptimizerException
from src.domain.services.portfolio_service import portfolio_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

blockchain_bp = Blueprint("blockchain", __name__, url_prefix="/api/v1/blockchain")


@blockchain_bp.route("/transactions/<int:portfolio_id>", methods=["GET"])
@jwt_required()
def get_transaction_history(portfolio_id: int) -> Response:
    """
    Get a portfolio's individual on-chain transaction log
    (PortfolioLedger.TransactionLogged events for its associated wallet
    address).
    ---
    parameters:
        - in: path
          name: portfolio_id
          type: integer
          required: true
    responses:
        200:
            description: Transaction history retrieved successfully.
        404:
            description: Portfolio not found, or has no associated wallet address.
        502:
            description: Blockchain node unreachable or the call failed.
    """
    try:
        logger.info(f"Get on-chain transaction history for portfolio {portfolio_id}")
        transactions = portfolio_service.get_onchain_transactions(portfolio_id)
        response = create_success_response(data={"transactions": transactions})
        return jsonify(response), 200

    except NotFoundError as e:
        logger.warning(f"Portfolio {portfolio_id} not found: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 404
    except BlockchainError as e:
        logger.error(
            f"Blockchain error getting transactions for portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"status": "error", "message": str(e)}), 502
    except RiskOptimizerException as e:
        logger.error(
            f"Error getting transactions for portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logger.error(
            f"Unexpected error getting transactions for portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@blockchain_bp.route("/verify/<int:portfolio_id>", methods=["GET"])
@jwt_required()
def verify_portfolio_integrity(portfolio_id: int) -> Response:
    """
    Compare a portfolio's database-recorded allocations against its current
    on-chain PortfolioTracker state.
    ---
    parameters:
        - in: path
          name: portfolio_id
          type: integer
          required: true
    responses:
        200:
            description: >
                Verification result. Always 200 when the portfolio exists,
                even if verification itself fails or is inconclusive (see
                the "verified" field) - this endpoint reports a status, it
                doesn't error out just because the chain disagrees with the
                database or is temporarily unreachable.
        404:
            description: Portfolio not found, or has no associated wallet address.
    """
    try:
        logger.info(f"Verify on-chain integrity for portfolio {portfolio_id}")
        result = portfolio_service.verify_onchain_integrity(portfolio_id)
        response = create_success_response(data=result)
        return jsonify(response), 200

    except NotFoundError as e:
        logger.warning(f"Portfolio {portfolio_id} not found: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 404
    except RiskOptimizerException as e:
        logger.error(
            f"Error verifying portfolio {portfolio_id}: {str(e)}", exc_info=True
        )
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logger.error(
            f"Unexpected error verifying portfolio {portfolio_id}: {str(e)}",
            exc_info=True,
        )
        return jsonify({"status": "error", "message": "Internal server error"}), 500
