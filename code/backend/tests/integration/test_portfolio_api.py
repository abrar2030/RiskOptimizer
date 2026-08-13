"""
Integration tests for Portfolio API.

Uses Flask's built-in test client and mocks all external dependencies
so no live server or database is required.
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


class TestPortfolioAPI(unittest.TestCase):

    def setUp(self):
        self._patches = _infra_patches()
        self.app, self.client = _make_test_client(self._patches)

        self.user_id = 42
        self.user_address = "0xPortfolioTestAddress"
        self.portfolio_id = 99
        self.access_token = "mock_access_token"

        # Mock JWT verify_token to always pass (patching at the verification level
        # since the @jwt_required() decorator is already bound at import time)
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
    # portfolio service mock responses
    # ------------------------------------------------------------------

    def _mock_portfolio(self, name="My First Portfolio", pid=None):
        return {
            "id": pid or self.portfolio_id,
            "name": name,
            "description": "A test portfolio for integration testing",
            "user_id": self.user_id,
            "user_address": self.user_address,
            "total_value": "0.00",
            "allocations": [],
        }

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_1_create_portfolio(self):
        """POST /portfolios → 201 with portfolio id and name."""
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.create_portfolio",
            return_value=self._mock_portfolio(),
        ):
            response = self.client.post(
                "/api/v1/portfolios",
                json={
                    "user_id": self.user_id,
                    "user_address": self.user_address,
                    "name": "My First Portfolio",
                    "description": "A test portfolio for integration testing",
                },
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            201,
            f"Expected 201, got {response.status_code}: {response.data}",
        )
        payload = response.get_json().get("data", response.get_json())
        self.assertIn("id", payload)
        self.assertEqual(payload["name"], "My First Portfolio")

    def test_2_save_portfolio_allocations(self):
        """POST /portfolios/save → 200 with allocations."""
        saved = {
            "name": "Updated Portfolio with Allocations",
            "user_address": self.user_address,
            "allocations": [
                {"asset": "BTC", "percentage": 60.0},
                {"asset": "ETH", "percentage": 40.0},
            ],
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.save_portfolio_allocations",
            return_value=saved,
        ):
            response = self.client.post(
                "/api/v1/portfolios/save",
                json={
                    "user_address": self.user_address,
                    "allocations": {"BTC": 60.0, "ETH": 40.0},
                    "name": "Updated Portfolio with Allocations",
                },
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        payload = response.get_json().get("data", response.get_json())
        self.assertIn("allocations", payload)
        self.assertEqual(len(payload["allocations"]), 2)
        self.assertEqual(payload["name"], "Updated Portfolio with Allocations")

    def test_3_get_portfolio_by_address(self):
        """GET /portfolios/address/<addr> → 200 with allocations."""
        portfolio_detail = {
            "user_address": self.user_address,
            "total_value": "10000.00",
            "allocations": [
                {"asset": "BTC", "percentage": 60.0},
                {"asset": "ETH", "percentage": 40.0},
            ],
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_portfolio_by_address",
            return_value=portfolio_detail,
        ):
            response = self.client.get(
                f"/api/v1/portfolios/address/{self.user_address}",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        payload = response.get_json().get("data", response.get_json())
        self.assertIn("total_value", payload)
        self.assertIn("allocations", payload)
        self.assertEqual(len(payload["allocations"]), 2)

    def test_4_update_portfolio(self):
        """PUT /portfolios/<id> → 200 with updated fields."""
        updated = {
            "id": self.portfolio_id,
            "name": "My First Portfolio",
            "description": "A much better description",
            "total_value": "5000.00",
            "user_id": self.user_id,
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.update_portfolio",
            return_value=updated,
        ):
            response = self.client.put(
                f"/api/v1/portfolios/{self.portfolio_id}",
                json={
                    "description": "A much better description",
                    "total_value": 5000.0,
                },
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        payload = response.get_json().get("data", response.get_json())
        self.assertEqual(payload["description"], "A much better description")
        self.assertEqual(payload["total_value"], "5000.00")

    def test_5_get_user_portfolios(self):
        """GET /portfolios/user/<id> → 200 with list of portfolios."""
        portfolios = [
            self._mock_portfolio("My First Portfolio", pid=1),
            self._mock_portfolio("My Second Portfolio", pid=2),
        ]
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_user_portfolios",
            return_value=portfolios,
        ):
            response = self.client.get(
                f"/api/v1/portfolios/user/{self.user_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        data = response.get_json().get("data", response.get_json())
        # data may be a list directly or wrapped in a pagination envelope
        portfolio_list = data if isinstance(data, list) else data.get("items", data)
        self.assertGreaterEqual(len(portfolio_list), 2)
        names = [p["name"] for p in portfolio_list]
        self.assertIn("My First Portfolio", names)
        self.assertIn("My Second Portfolio", names)

    def test_6_delete_portfolio(self):
        """DELETE /portfolios/<id> → 204; subsequent GET → 404."""
        from src.core.exceptions import NotFoundError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.delete_portfolio",
            return_value=True,
        ):
            response = self.client.delete(
                f"/api/v1/portfolios/{self.portfolio_id}",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            204,
            f"Expected 204, got {response.status_code}: {response.data}",
        )

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_portfolio_by_address",
            side_effect=NotFoundError(
                f"Portfolio for address {self.user_address} not found"
            ),
        ):
            get_response = self.client.get(
                f"/api/v1/portfolios/address/{self.user_address}",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            get_response.status_code,
            404,
            f"Expected 404, got {get_response.status_code}: {get_response.data}",
        )

    def test_7_get_onchain_portfolio(self):
        """GET /portfolios/address/<addr>/onchain → 200 with on-chain data."""
        onchain_portfolio = {
            "user_address": self.user_address,
            "assets": ["BTC", "ETH"],
            "allocations": [0.6, 0.4],
            "updated_at": 1_700_000_000,
            "version": 1,
            "source": "blockchain",
            "network": "Custom (BLOCKCHAIN_PROVIDER)",
        }
        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_portfolio",
            return_value=onchain_portfolio,
        ):
            response = self.client.get(
                f"/api/v1/portfolios/address/{self.user_address}/onchain",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            200,
            f"Expected 200, got {response.status_code}: {response.data}",
        )
        payload = response.get_json().get("data", response.get_json())
        self.assertEqual(payload["assets"], ["BTC", "ETH"])
        self.assertEqual(payload["version"], 1)

    def test_8_get_onchain_portfolio_not_found(self):
        """GET .../onchain → 404 when no on-chain portfolio has been recorded."""
        from src.core.exceptions import NotFoundError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_portfolio",
            side_effect=NotFoundError(
                f"On-chain portfolio for {self.user_address} not found",
                "onchain_portfolio",
                self.user_address,
            ),
        ):
            response = self.client.get(
                f"/api/v1/portfolios/address/{self.user_address}/onchain",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            404,
            f"Expected 404, got {response.status_code}: {response.data}",
        )

    def test_9_get_onchain_portfolio_blockchain_error(self):
        """GET .../onchain → 502 when the blockchain node is unreachable."""
        from src.core.exceptions import BlockchainError

        with patch(
            "src.domain.services.portfolio_service.portfolio_service.get_onchain_portfolio",
            side_effect=BlockchainError("Failed to read on-chain portfolio: timeout"),
        ):
            response = self.client.get(
                f"/api/v1/portfolios/address/{self.user_address}/onchain",
                headers=self._auth_headers(),
            )
        self.assertEqual(
            response.status_code,
            502,
            f"Expected 502, got {response.status_code}: {response.data}",
        )


if __name__ == "__main__":
    unittest.main()
