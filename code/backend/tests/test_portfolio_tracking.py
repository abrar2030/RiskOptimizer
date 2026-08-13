"""
Portfolio Tracking Tests for RiskOptimizer.

Patches Web3 in its canonical location (blockchain.services.blockchain_service)
rather than in the proxy stub, so mocks are correctly intercepted.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from src.services.ai_optimization import AIOptimizationService

# Import BlockchainService via the proxy — the class itself lives in
# blockchain.services.blockchain_service, which is where Web3 must be patched.
from src.services.blockchain_service import BlockchainService

# Canonical module path where Web3 is *used* (not where it is imported from).
_BC_MODULE = "blockchain.services.blockchain_service"


class TestPortfolioTracking:
    """Test suite for portfolio tracking functionality."""

    @pytest.fixture
    def sample_portfolio(self) -> None:
        """Sample portfolio data for testing."""
        return {
            "user_address": "0x1234567890123456789012345678901234567890",
            "assets": ["BTC", "ETH", "AAPL", "MSFT", "GOOGL"],
            "allocations": [0.25, 0.25, 0.2, 0.15, 0.15],
        }

    @pytest.fixture
    def sample_market_data(self) -> None:
        """Sample market data for testing."""
        dates = pd.date_range(start="2022-01-01", end="2023-01-01", freq="B")
        assets = ["BTC", "ETH", "AAPL", "MSFT", "GOOGL", "market_index"]
        np.random.seed(42)
        data = pd.DataFrame(index=dates)
        for asset in assets:
            volatility = 0.03 if asset in ["BTC", "ETH"] else 0.015
            returns = np.random.normal(0.0005, volatility, size=len(dates))
            prices = 100 * np.cumprod(1 + returns)
            data[asset] = prices
        return data

    # ------------------------------------------------------------------
    # AI optimisation tests (no blockchain)
    # ------------------------------------------------------------------

    def test_portfolio_optimization(
        self, sample_market_data: "np.ndarray | pd.DataFrame | list"
    ) -> None:
        """Test portfolio optimization with AI models."""
        optimizer = AIOptimizationService()
        result = optimizer.optimize_portfolio(sample_market_data, risk_tolerance=5)

        assert "optimized_allocation" in result
        assert "performance_metrics" in result
        for field in ["expected_return", "volatility", "sharpe_ratio"]:
            assert field in result["performance_metrics"]

        allocations = result["optimized_allocation"]
        total = sum(allocations.values())
        assert 0.99 < total < 1.01, f"Weights sum to {total}, expected ~1.0"
        for asset in sample_market_data.columns:
            if asset != "market_index":
                assert asset in allocations, f"Missing asset: {asset}"

    def test_risk_simulation(
        self,
        sample_market_data: "np.ndarray | pd.DataFrame | list",
        sample_portfolio: object,
    ) -> None:
        """Test Monte Carlo risk simulation."""
        optimizer = AIOptimizationService()
        weights = dict(zip(sample_portfolio["assets"], sample_portfolio["allocations"]))
        result = optimizer.run_risk_simulation(sample_market_data, weights)

        assert "risk_metrics" in result
        assert "simulation_summary" in result
        rm = result["risk_metrics"]
        for field in [
            "expected_final_value",
            "value_at_risk_95",
            "value_at_risk_99",
            "max_drawdown",
        ]:
            assert field in rm, f"Missing risk metric: {field}"

        ss = result["simulation_summary"]
        assert "initial_value" in ss
        assert "percentiles" in ss
        assert "p50" in ss["percentiles"]

        assert rm["expected_final_value"] > 0
        assert rm["value_at_risk_95"] > 0
        assert rm["value_at_risk_99"] > 0

    # ------------------------------------------------------------------
    # Blockchain tests — patch Web3 where it is *consumed*
    # ------------------------------------------------------------------

    @patch(f"{_BC_MODULE}.Web3")
    def test_blockchain_portfolio_retrieval(
        self, mock_web3: "MagicMock", sample_portfolio: object
    ) -> None:
        """Test portfolio retrieval from blockchain (mocked)."""
        mock_contract = MagicMock()
        # PortfolioTracker.getPortfolio returns
        # (assets, allocations, updatedAt, version) on-chain; the mock must
        # match that 4-value shape or BlockchainService.get_portfolio's
        # unpacking will fail exactly as it would against the real contract.
        mock_contract.functions.getPortfolio.return_value.call.return_value = (
            sample_portfolio["assets"],
            [int(alloc * 10000) for alloc in sample_portfolio["allocations"]],
            1_700_000_000,
            1,
        )
        mock_web3.return_value.eth.contract.return_value = mock_contract
        mock_web3.return_value.is_connected.return_value = True
        mock_web3.return_value.is_address.return_value = True
        mock_web3.to_checksum_address = lambda x: x

        service = BlockchainService()
        result = service.get_portfolio(sample_portfolio["user_address"])

        assert result is not None
        assert result["user_address"] == sample_portfolio["user_address"]
        assert result["assets"] == sample_portfolio["assets"]
        assert result["updated_at"] == 1_700_000_000
        assert result["version"] == 1
        for i, alloc in enumerate(result["allocations"]):
            assert abs(alloc - sample_portfolio["allocations"][i]) < 0.0001

    @patch(f"{_BC_MODULE}.Web3")
    def test_blockchain_portfolio_update(
        self, mock_web3: "MagicMock", sample_portfolio: object
    ) -> None:
        """Test portfolio update on blockchain (mocked)."""
        mock_contract = MagicMock()

        # Mock signed transaction — support both web3.py v5 and v6 attribute names
        mock_signed_tx = MagicMock()
        mock_signed_tx.raw_transaction = b"rawbytes"
        mock_signed_tx.rawTransaction = b"rawbytes"

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xabcdef1234567890"

        mock_receipt = MagicMock()
        mock_receipt.status = 1
        mock_receipt.blockNumber = 12345
        mock_receipt.gasUsed = 100000

        mock_account = MagicMock()
        mock_account.address = sample_portfolio["user_address"]
        mock_account.sign_transaction.return_value = mock_signed_tx

        mock_web3.return_value.eth.send_raw_transaction.return_value = mock_tx_hash
        mock_web3.return_value.eth.wait_for_transaction_receipt.return_value = (
            mock_receipt
        )
        mock_web3.return_value.eth.contract.return_value = mock_contract
        mock_web3.return_value.eth.gas_price = 20_000_000_000
        mock_web3.return_value.eth.get_transaction_count.return_value = 1
        mock_web3.return_value.is_connected.return_value = True
        mock_web3.return_value.is_address.return_value = True
        mock_web3.to_checksum_address = lambda x: x

        service = BlockchainService()
        service.account = mock_account

        result = service.update_portfolio(
            sample_portfolio["user_address"],
            sample_portfolio["assets"],
            sample_portfolio["allocations"],
        )

        assert result is not None
        assert result["tx_hash"] == "0xabcdef1234567890"
        assert result["status"] == "success"
        assert result["block_number"] == 12345
        assert result["gas_used"] == 100000

    def test_portfolio_optimization_with_risk_tolerance(
        self, sample_market_data: "np.ndarray | pd.DataFrame | list"
    ) -> None:
        """Test portfolio optimization with different risk tolerance levels."""
        optimizer = AIOptimizationService()
        low_result = optimizer.optimize_portfolio(sample_market_data, risk_tolerance=2)
        high_result = optimizer.optimize_portfolio(sample_market_data, risk_tolerance=8)

        for result in (low_result, high_result):
            assert "optimized_allocation" in result
            assert "performance_metrics" in result
            weights = result["optimized_allocation"]
            assert abs(sum(weights.values()) - 1.0) < 0.01

    @patch(f"{_BC_MODULE}.Web3")
    def test_multi_network_support(self, mock_web3: "MagicMock") -> None:
        """Test blockchain service with multiple networks."""
        mock_web3.return_value.is_connected.return_value = True

        service = BlockchainService(network="ethereum")
        networks = service.get_supported_networks()

        assert "ethereum" in networks
        assert "polygon" in networks
        assert "goerli" in networks

        mock_web3.return_value.is_connected.return_value = True
        result = service.switch_network("polygon")
        assert result is True
        assert service.network == "polygon"

    def test_integrated_portfolio_optimization_and_tracking(
        self,
        sample_market_data: "np.ndarray | pd.DataFrame | list",
        sample_portfolio: object,
    ) -> None:
        """Test integration between AI optimization and blockchain tracking (mocked blockchain)."""
        ai_service = AIOptimizationService()
        blockchain_service = MagicMock()
        blockchain_service.update_portfolio.return_value = {
            "tx_hash": "0xabcdef1234567890",
            "status": "success",
        }

        optimization_result = ai_service.optimize_portfolio(sample_market_data, 5)
        optimized_weights = optimization_result["optimized_allocation"]
        assets = list(optimized_weights.keys())
        allocations = list(optimized_weights.values())

        blockchain_result = blockchain_service.update_portfolio(
            sample_portfolio["user_address"], assets, allocations
        )

        blockchain_service.update_portfolio.assert_called_once()
        assert blockchain_result["status"] == "success"
        assert len(assets) > 0
        assert 0.99 < sum(allocations) < 1.01
