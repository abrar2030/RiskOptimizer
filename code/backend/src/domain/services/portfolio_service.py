import logging
from decimal import Decimal, getcontext
from typing import Any, Dict, List, Optional

from src.core.exceptions import BlockchainError, NotFoundError, ValidationError
from src.domain.services.audit_service import audit_service
from src.infrastructure.cache.redis_cache import redis_cache
from src.infrastructure.database.repositories.portfolio_repository import (
    portfolio_repository,
)
from src.infrastructure.database.repositories.user_repository import user_repository
from src.infrastructure.database.session import get_db_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

getcontext().prec = 28


class PortfolioService:
    """
    Service for managing user portfolios and their allocations.

    Handles retrieving, saving, creating, updating, and deleting portfolios.
    Integrates with the database repository, Redis caching, and audit service.
    """

    def __init__(self) -> None:
        self.portfolio_repo = portfolio_repository
        self.user_repo = user_repository
        self.cache = redis_cache
        self.audit_service = audit_service

    def get_portfolio_by_address(self, user_address: str) -> Dict[str, Any]:
        """
        Retrieves a user's portfolio and its allocations by wallet address.

        Raises:
            ValidationError: If the user address is invalid.
            NotFoundError: If no portfolio is found for the given address.
        """
        if not user_address or not isinstance(user_address, str):
            raise ValidationError(
                "User address is required", "user_address", user_address
            )
        cache_key = f"portfolio:{user_address}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            logger.debug(f"Portfolio cache hit for address {user_address}")
            if "total_value" in cached_data:
                cached_data["total_value"] = Decimal(str(cached_data["total_value"]))
            if "allocations" in cached_data:
                for alloc in cached_data["allocations"]:
                    alloc["percentage"] = Decimal(str(alloc["percentage"]))
                    if alloc.get("amount") is not None:
                        alloc["amount"] = Decimal(str(alloc["amount"]))
                    if alloc.get("current_price") is not None:
                        alloc["current_price"] = Decimal(str(alloc["current_price"]))
            return cached_data

        with get_db_session() as session:
            portfolio_data = self.portfolio_repo.get_portfolio_with_allocations(
                user_address, session
            )
            serializable_portfolio_data = portfolio_data.copy()
            if "total_value" in serializable_portfolio_data:
                serializable_portfolio_data["total_value"] = str(
                    serializable_portfolio_data["total_value"]
                )
            if "allocations" in serializable_portfolio_data:
                serializable_portfolio_data["allocations"] = [
                    {
                        k: str(v) if isinstance(v, Decimal) else v
                        for k, v in alloc.items()
                    }
                    for alloc in serializable_portfolio_data["allocations"]
                ]
            self.cache.set(cache_key, serializable_portfolio_data, ttl=300)
            logger.info(f"Retrieved portfolio for address {user_address}")
            return portfolio_data

    def get_onchain_portfolio(self, user_address: str) -> Dict[str, Any]:
        """
        Retrieves a user's portfolio directly from the blockchain
        (PortfolioTracker contract), independent of the database-backed
        portfolio returned by get_portfolio_by_address. Useful for
        verifying on-chain state matches what's recorded off-chain, or for
        users who only ever interact via the smart contract directly.

        Raises:
            ValidationError: If the user address is invalid.
            NotFoundError: If no portfolio has ever been recorded on-chain
                for this address (version 0).
            BlockchainError: If the blockchain node is unreachable or the
                call otherwise fails.
        """
        if not user_address or not isinstance(user_address, str):
            raise ValidationError(
                "User address is required", "user_address", user_address
            )

        # Imported lazily so a missing/unreachable blockchain endpoint (or
        # missing web3 dependency) only affects this specific optional
        # feature, not every portfolio operation - the rest of
        # PortfolioService is fully DB-backed and must keep working
        # regardless of blockchain availability.
        from src.services.blockchain_service import get_blockchain_service

        try:
            service = get_blockchain_service()
            if not service.validate_address(user_address):
                raise ValidationError(
                    "Invalid Ethereum address", "user_address", user_address
                )
            onchain_data = service.get_portfolio(user_address)
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error reading on-chain portfolio: {e}", exc_info=True)
            raise BlockchainError(f"Failed to read on-chain portfolio: {e}") from e

        if onchain_data is None:
            raise BlockchainError("Blockchain call failed unexpectedly")
        if onchain_data.get("version", 0) == 0:
            raise NotFoundError(
                f"On-chain portfolio for {user_address} not found",
                "onchain_portfolio",
                user_address,
            )

        logger.info(f"Retrieved on-chain portfolio for address {user_address}")
        return onchain_data

    def get_onchain_transactions(
        self, portfolio_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get an individual buy/sell/rebalance transaction log for a
        portfolio from the PortfolioLedger contract, keyed by the
        portfolio's associated on-chain wallet address
        (Portfolio.user_address).

        Distinct from get_onchain_portfolio(): that reads the current
        PortfolioTracker allocation snapshot for an address directly; this
        reads the append-only PortfolioLedger transaction history for the
        address associated with a specific database portfolio record.

        Raises:
            NotFoundError: If the portfolio doesn't exist, or has no
                associated wallet address.
            BlockchainError: If the blockchain node is unreachable or the
                call otherwise fails.
        """
        portfolio = self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            raise NotFoundError(
                f"Portfolio {portfolio_id} not found", "portfolio", str(portfolio_id)
            )
        if not portfolio.user_address:
            raise NotFoundError(
                f"Portfolio {portfolio_id} has no associated wallet address",
                "portfolio",
                str(portfolio_id),
            )

        from src.services.blockchain_service import get_blockchain_service

        try:
            service = get_blockchain_service()
            raw_transactions = service.get_ledger_transactions(
                portfolio.user_address, limit=limit
            )
        except Exception as e:
            logger.error(f"Error reading on-chain transactions: {e}", exc_info=True)
            raise BlockchainError(f"Failed to read on-chain transactions: {e}") from e

        transactions = [
            {
                "tx_hash": tx["tx_hash"],
                "action": tx["action"].lower(),
                "symbol": tx["symbol"],
                "quantity": tx["quantity"],
                "value": tx["quantity"] * tx["price"],
                "timestamp": tx["timestamp"] * 1000,  # seconds -> ms for JS Date
                "status": tx["status"],
                "block_number": tx["block_number"],
                "explorer_url": tx["explorer_url"],
            }
            for tx in raw_transactions
        ]
        logger.info(
            f"Retrieved {len(transactions)} on-chain transactions for portfolio {portfolio_id}"
        )
        return transactions

    def verify_onchain_integrity(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Compare a portfolio's database-recorded allocations against its
        current on-chain PortfolioTracker state.

        Raises:
            NotFoundError: If the portfolio doesn't exist, or has no
                associated wallet address.
        """
        portfolio = self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            raise NotFoundError(
                f"Portfolio {portfolio_id} not found", "portfolio", str(portfolio_id)
            )
        if not portfolio.user_address:
            raise NotFoundError(
                f"Portfolio {portfolio_id} has no associated wallet address",
                "portfolio",
                str(portfolio_id),
            )

        from src.services.blockchain_service import get_blockchain_service

        try:
            service = get_blockchain_service()
            onchain = service.get_portfolio(portfolio.user_address)
        except Exception as e:
            logger.error(f"Error verifying on-chain integrity: {e}", exc_info=True)
            # A verification check should report "unverified", not error
            # out, when the chain is temporarily unreachable - the caller
            # still gets a usable (if inconclusive) response.
            return {
                "verified": False,
                "blockchain": self._get_network_name(),
                "last_verification": None,
                "reason": f"Blockchain unreachable: {e}",
            }

        import time as _time

        if onchain is None or onchain.get("version", 0) == 0:
            return {
                "verified": False,
                "blockchain": self._get_network_name(),
                "last_verification": int(_time.time() * 1000),
                "reason": "No on-chain portfolio recorded for this address",
            }

        db_allocations = {
            alloc.asset_symbol: float(alloc.percentage)
            for alloc in (portfolio.allocations or [])
        }
        onchain_allocations = dict(zip(onchain["assets"], onchain["allocations"]))
        # DB fractions/percentages and on-chain fractions are compared with
        # a small tolerance for rounding rather than exact equality.
        matches = len(db_allocations) == len(onchain_allocations) and all(
            asset in onchain_allocations
            and abs(onchain_allocations[asset] * 100 - pct) < 0.5
            for asset, pct in db_allocations.items()
        )

        return {
            "verified": matches,
            "blockchain": self._get_network_name(),
            "last_verification": int(_time.time() * 1000),
            "onchain_version": onchain.get("version"),
            "onchain_updated_at": onchain.get("updated_at"),
        }

    def _get_network_name(self) -> str:
        try:
            from src.services.blockchain_service import get_blockchain_service

            return get_blockchain_service().network_config.get("name", "unknown")
        except Exception:
            return "unknown"

    def save_portfolio(
        self,
        user_address: str,
        allocations: Dict[str, float],
        name: str = "Default Portfolio",
    ) -> Dict[str, Any]:
        """
        Saves or updates a user's portfolio allocations.

        Raises:
            ValidationError: If input data is invalid.
        """
        self._validate_portfolio_input(user_address, allocations, name)
        normalized_allocations = self._normalize_allocations(allocations)
        decimal_allocations = {
            k: Decimal(str(v)) for k, v in normalized_allocations.items()
        }
        with get_db_session() as session:
            portfolio_data = self.portfolio_repo.save_portfolio_with_allocations(
                user_address, decimal_allocations, name, session
            )
            user = self.user_repo.get_by_wallet_address(user_address, session)
            user_id = user.id if user else None
            self.audit_service.log_action(
                user_id=user_id,
                action_type="PORTFOLIO_SAVED",
                entity_type="PORTFOLIO",
                entity_id=portfolio_data.get("portfolio_id"),
                details={
                    "user_address": user_address,
                    "name": name,
                    "allocations": {k: str(v) for k, v in decimal_allocations.items()},
                },
            )
            cache_key = f"portfolio:{user_address}"
            self.cache.delete(cache_key)
            logger.info(
                f"Saved portfolio for address {user_address} with {len(decimal_allocations)} assets"
            )
            return portfolio_data

    def save_portfolio_allocations(
        self,
        user_address: str,
        allocations: Dict[str, float],
        name: str = "Default Portfolio",
    ) -> Dict[str, Any]:
        """
        Alias for save_portfolio for API compatibility.

        Saves or updates a user's portfolio allocations.
        """
        return self.save_portfolio(user_address, allocations, name)

    def create_portfolio(
        self,
        user_id: int,
        user_address: str,
        name: str = "Default Portfolio",
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a new portfolio for a specified user.

        Raises:
            ValidationError: If input data is invalid.
            NotFoundError: If the specified user does not exist.
        """
        if not user_id or not isinstance(user_id, int):
            raise ValidationError(
                "User ID is required and must be an integer.", "user_id", user_id
            )
        if not user_address or not isinstance(user_address, str):
            raise ValidationError(
                "User address is required and must be a string.",
                "user_address",
                user_address,
            )
        if not name or not isinstance(name, str):
            raise ValidationError(
                "Portfolio name is required and must be a string.", "name", name
            )
        with get_db_session() as session:
            user = self.user_repo.get_by_id(user_id, session)
            if not user:
                raise NotFoundError(f"User {user_id} not found", "user", str(user_id))
            portfolio = self.portfolio_repo.create(
                user_id, user_address, name, description, session
            )
            portfolio_data = {
                "id": portfolio.id,
                "user_id": portfolio.user_id,
                "user_address": portfolio.user_address,
                "name": portfolio.name,
                "description": portfolio.description,
                "total_value": (
                    str(portfolio.total_value)
                    if isinstance(portfolio.total_value, Decimal)
                    else portfolio.total_value
                ),
                "created_at": portfolio.created_at.isoformat(),
                "updated_at": portfolio.updated_at.isoformat(),
            }
            self.audit_service.log_action(
                user_id=user_id,
                action_type="PORTFOLIO_CREATED",
                entity_type="PORTFOLIO",
                entity_id=portfolio.id,
                details={
                    "name": name,
                    "user_address": user_address,
                    "description": description,
                },
            )
            logger.info(f"Created portfolio {portfolio.id} for user {user_id}")
            return portfolio_data

    def update_portfolio(
        self, portfolio_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates an existing portfolio's details.

        Raises:
            ValidationError: If input data is invalid.
            NotFoundError: If the portfolio is not found.
        """
        if not portfolio_id or not isinstance(portfolio_id, int):
            raise ValidationError(
                "Portfolio ID is required and must be an integer.",
                "portfolio_id",
                portfolio_id,
            )
        if not data or not isinstance(data, dict):
            raise ValidationError(
                "Update data is required and must be a non-empty dictionary.",
                "data",
                data,
            )
        allowed_fields = {"name", "description", "total_value"}
        processed_data = {}
        for key, value in data.items():
            if key not in allowed_fields:
                raise ValidationError(f"Invalid field for update: {key}", "data", data)
            if key == "total_value":
                try:
                    processed_data[key] = Decimal(str(value))
                except Exception:
                    raise ValidationError(
                        "Total value must be a valid number.", "total_value", value
                    )
            else:
                processed_data[key] = value

        with get_db_session() as session:
            old_portfolio = self.portfolio_repo.get_by_id(portfolio_id, session)
            if not old_portfolio:
                raise NotFoundError(
                    f"Portfolio {portfolio_id} not found",
                    "portfolio",
                    str(portfolio_id),
                )
            portfolio = self.portfolio_repo.update(
                portfolio_id, processed_data, session
            )
            if portfolio and portfolio.user_address:
                cache_key = f"portfolio:{portfolio.user_address}"
                self.cache.delete(cache_key)
            portfolio_data = {
                "id": portfolio.id,
                "user_id": portfolio.user_id,
                "user_address": portfolio.user_address,
                "name": portfolio.name,
                "description": portfolio.description,
                "total_value": (
                    str(portfolio.total_value)
                    if isinstance(portfolio.total_value, Decimal)
                    else portfolio.total_value
                ),
                "created_at": portfolio.created_at.isoformat(),
                "updated_at": portfolio.updated_at.isoformat(),
            }
            self.audit_service.log_action(
                user_id=portfolio.user_id,
                action_type="PORTFOLIO_UPDATED",
                entity_type="PORTFOLIO",
                entity_id=portfolio.id,
                details={
                    "old_data": {
                        k: str(getattr(old_portfolio, k))
                        for k in processed_data.keys()
                        if hasattr(old_portfolio, k)
                    },
                    "new_data": {k: str(v) for k, v in processed_data.items()},
                },
            )
            logger.info(f"Updated portfolio {portfolio_id}")
            return portfolio_data

    def delete_portfolio(self, portfolio_id: int) -> bool:
        """
        Deletes a portfolio from the system.

        Raises:
            ValidationError: If the portfolio ID is invalid.
        """
        if not portfolio_id or not isinstance(portfolio_id, int):
            raise ValidationError(
                "Portfolio ID is required and must be an integer.",
                "portfolio_id",
                portfolio_id,
            )
        with get_db_session() as session:
            portfolio = self.portfolio_repo.get_by_id(portfolio_id, session)
            deleted = self.portfolio_repo.delete(portfolio_id, session)
            if deleted and portfolio and portfolio.user_address:
                cache_key = f"portfolio:{portfolio.user_address}"
                self.cache.delete(cache_key)
            if deleted:
                logger.info(f"Deleted portfolio {portfolio_id}")
                self.audit_service.log_action(
                    user_id=portfolio.user_id,
                    action_type="PORTFOLIO_DELETED",
                    entity_type="PORTFOLIO",
                    entity_id=portfolio.id,
                    details={
                        "portfolio_id": portfolio.id,
                        "name": portfolio.name,
                        "user_address": portfolio.user_address,
                    },
                )
            else:
                logger.warning(f"Portfolio {portfolio_id} not found for deletion")
            return deleted

    def get_user_portfolios(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all portfolios associated with a specific user ID.

        Raises:
            ValidationError: If the user ID is invalid.
        """
        if not user_id or not isinstance(user_id, int):
            raise ValidationError(
                "User ID is required and must be an integer.", "user_id", user_id
            )
        with get_db_session() as session:
            portfolios = self.portfolio_repo.get_by_user_id(user_id, session)
            portfolio_list = []
            for portfolio in portfolios:
                portfolio_data = {
                    "id": portfolio.id,
                    "user_id": portfolio.user_id,
                    "user_address": portfolio.user_address,
                    "name": portfolio.name,
                    "description": portfolio.description,
                    "total_value": (
                        str(portfolio.total_value)
                        if isinstance(portfolio.total_value, Decimal)
                        else portfolio.total_value
                    ),
                    "created_at": portfolio.created_at.isoformat(),
                    "updated_at": portfolio.updated_at.isoformat(),
                }
                portfolio_list.append(portfolio_data)
            logger.info(
                f"Retrieved {len(portfolio_list)} portfolios for user {user_id}"
            )
            return portfolio_list

    def _validate_portfolio_input(
        self, user_address: str, allocations: Dict[str, float], name: str
    ) -> None:
        """Internal helper to validate common portfolio input parameters."""
        if not user_address or not isinstance(user_address, str):
            raise ValidationError(
                "User address is required and must be a string.",
                "user_address",
                user_address,
            )
        if not allocations or not isinstance(allocations, dict):
            raise ValidationError(
                "Allocations are required and must be a dictionary.",
                "allocations",
                allocations,
            )
        if len(allocations) == 0:
            raise ValidationError(
                "At least one allocation is required.", "allocations", allocations
            )
        for asset, percentage in allocations.items():
            if not isinstance(asset, str) or not asset.strip():
                raise ValidationError(
                    f"Invalid asset symbol: {asset}. Asset symbol must be a non-empty string.",
                    "allocations",
                    allocations,
                )
            try:
                Decimal(str(percentage))
            except Exception:
                raise ValidationError(
                    f"Invalid percentage for asset {asset}. Must be a valid number.",
                    "allocations",
                    allocations,
                )
            if not 0 <= percentage <= 100:
                raise ValidationError(
                    f"Percentage for asset {asset} must be between 0 and 100.",
                    "allocations",
                    allocations,
                )
        if not name or not isinstance(name, str) or not name.strip():
            raise ValidationError(
                "Portfolio name is required and must be a non-empty string.",
                "name",
                name,
            )

    def _normalize_allocations(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Normalizes portfolio allocations so that their sum is 100%."""
        total_percentage = sum(allocations.values())
        if total_percentage == 0:
            raise ValidationError(
                "Total allocation percentage cannot be zero.",
                "allocations",
                allocations,
            )
        normalized = {
            asset: percentage / total_percentage * 100
            for asset, percentage in allocations.items()
        }
        return normalized


portfolio_service = PortfolioService()
