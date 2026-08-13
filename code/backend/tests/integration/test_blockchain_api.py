"""
Integration tests for the Blockchain API (transaction history + portfolio
integrity verification, keyed by database portfolio_id).

Uses Flask's built-in test client and mocks all external dependencies so no
live server, database, or blockchain node is required.
"""

import logging
import unittest
from unittest.mock import MagicMock, patch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _infra_patches():
    return [
        patch("src.infrastructure.database.session.init_db", return_value=None),
        patch(
            "src.infrastructure.database.session.check_db_connection", return_value=True
        ),
        patch(
            "src.api.middleware.rate_limit_middleware.apply_rate_limiting",
            return_value=None,
        ),
        patch("src.utils.performance.apply_performance_monitoring", return_value=None),
    ]


def _make_test_client(patches):
    mock_redis = MagicMock()
    mock_redis.health_check.return_value = True
    redis_patch = patch("src.infrastructure.cache.redis_cache.redis_cache", mock_redis)
    patches.append(redis_patch)
    for p in patches:
        p.start()
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app, app.test_client()


class TestBlockchainAPI(unittest.TestCase):

    def setUp(self):
        self._patches = _infra_patches()
        self.app, self.client = _make_test_client(self._patches)

        self.portfolio_id = 99
        self.access_token = "mock_access_token"

        self._jwt_patch = patch(
            "src.domain.services.auth_service.auth_service.verify_token",
            return_value={"user_id": 1, "email": "test@example.com", "role": "user"},
        )
        self._jwt_patch.start()
        self._patches.append(self._jwt_patch)

    def tearDown(self):
        for p in self._patches:
            try:
                p.stop()
            except RuntimeError:
                pass

    def _auth_headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    # ------------------------------------------------------------------

    def test_get_transaction_history_success(self):
        """GET /blockchain/transactions/<id> → 200 with reshaped tx list."""
        mock_transactions = [
            {
                "tx_hash": "0xabc123",
                "action": "buy",
                "symbol": "BTC",
                "quantity": 2,
                "value": 130000,
                "timestamp": 1_700_000_000_000,
                "status": "confirmed",
                "block_number": 42,
                "explorer_url": "/tx/0xabc123",
            }
        ]
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_transactions",
            return_value=mock_transactions,
        ):
            response = self.client.get(
                f"/api/v1/blockchain/transactions/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        payload = response.get_json()["data"]
        self.assertEqual(len(payload["transactions"]), 1)
        self.assertEqual(payload["transactions"][0]["action"], "buy")
        self.assertEqual(payload["transactions"][0]["symbol"], "BTC")

    def test_get_transaction_history_not_found(self):
        """GET /blockchain/transactions/<id> → 404 when the portfolio doesn't exist."""
        from src.core.exceptions import NotFoundError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_transactions",
            side_effect=NotFoundError(
                f"Portfolio {self.portfolio_id} not found",
                "portfolio",
                str(self.portfolio_id),
            ),
        ):
            response = self.client.get(
                f"/api/v1/blockchain/transactions/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 404)

    def test_get_transaction_history_blockchain_error(self):
        """GET /blockchain/transactions/<id> → 502 when the chain is unreachable."""
        from src.core.exceptions import BlockchainError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_transactions",
            side_effect=BlockchainError(
                "Failed to read on-chain transactions: timeout"
            ),
        ):
            response = self.client.get(
                f"/api/v1/blockchain/transactions/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 502)

    def test_verify_portfolio_integrity_verified(self):
        """GET /blockchain/verify/<id> → 200, verified=True when DB matches on-chain."""
        mock_result = {
            "verified": True,
            "blockchain": "Custom (BLOCKCHAIN_PROVIDER)",
            "last_verification": 1_700_000_000_000,
            "onchain_version": 1,
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.verify_onchain_integrity",
            return_value=mock_result,
        ):
            response = self.client.get(
                f"/api/v1/blockchain/verify/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertTrue(payload["verified"])

    def test_verify_portfolio_integrity_not_verified(self):
        """GET /blockchain/verify/<id> → 200 (not 4xx/5xx) when the chain
        disagrees with the DB or is unreachable - this is a reportable
        status, not an error."""
        mock_result = {
            "verified": False,
            "blockchain": "Custom (BLOCKCHAIN_PROVIDER)",
            "last_verification": None,
            "reason": "Blockchain unreachable: timeout",
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.verify_onchain_integrity",
            return_value=mock_result,
        ):
            response = self.client.get(
                f"/api/v1/blockchain/verify/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["data"]
        self.assertFalse(payload["verified"])

    def test_verify_portfolio_integrity_not_found(self):
        """GET /blockchain/verify/<id> → 404 when the portfolio doesn't exist."""
        from src.core.exceptions import NotFoundError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.verify_onchain_integrity",
            side_effect=NotFoundError(
                f"Portfolio {self.portfolio_id} not found",
                "portfolio",
                str(self.portfolio_id),
            ),
        ):
            response = self.client.get(
                f"/api/v1/blockchain/verify/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(response.status_code, 404)

    def test_requires_auth(self):
        """Both routes require a JWT; no Authorization header → 401."""
        r1 = self.client.get(f"/api/v1/blockchain/transactions/{self.portfolio_id}")
        r2 = self.client.get(f"/api/v1/blockchain/verify/{self.portfolio_id}")
        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r2.status_code, 401)


if __name__ == "__main__":
    unittest.main()
