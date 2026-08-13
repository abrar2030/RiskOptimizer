"""
Blockchain Integration Service for RiskOptimizer

This service provides integration with blockchain smart contracts for:
1. Portfolio tracking on the blockchain
2. Risk management calculations
3. Transaction handling and verification
4. Multi-chain support for portfolio diversification
"""

import json
import logging
import os
from typing import Dict

from dotenv import load_dotenv
from eth_account import Account
from web3 import HTTPProvider, Web3

try:
    from web3.middleware import ExtraDataToPOAMiddleware
except ImportError:
    try:
        from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
    except ImportError:
        ExtraDataToPOAMiddleware = None

try:
    from web3.gas_strategies.time_based import medium_gas_price_strategy
except ImportError:
    medium_gas_price_strategy = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

# ABI helpers ---------------------------------------------------------------
#
# The embedded ABI fallbacks below are kept in sync with the actual Solidity
# contracts (see ../contracts/*.sol and their compiled artifacts). Whenever
# possible, the real Hardhat build artifact is loaded instead so the ABI can
# never silently drift from the deployed bytecode.

_ARTIFACTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "artifacts",
    "contracts",
)


def _load_abi(contract_filename: str, contract_name: str, fallback_abi: list) -> list:
    """
    Load a contract ABI from the compiled Hardhat artifact if available,
    otherwise fall back to the embedded copy below. Keeping a fallback lets
    this module import cleanly even when the contracts haven't been compiled
    (e.g. a Python-only deployment of the backend).
    """
    artifact_path = os.path.join(
        _ARTIFACTS_DIR, f"{contract_filename}.sol", f"{contract_name}.json"
    )
    try:
        with open(artifact_path, encoding="utf-8") as f:
            return json.load(f)["abi"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        logger.debug(
            "Compiled artifact for %s not found at %s; using embedded ABI.",
            contract_name,
            artifact_path,
        )
        return fallback_abi


# Fallback ABI: mirrors PortfolioTracker.sol. getPortfolio returns
# (assets, allocations, updatedAt, version); the previous 2-value ABI here
# silently dropped the trailing return values and would misdecode any real
# call to the deployed contract.
_PORTFOLIO_TRACKER_ABI_FALLBACK = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "user",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "asset",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "newAllocationBps",
                "type": "uint256",
            },
        ],
        "name": "AssetRebalanced",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "user",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "version",
                "type": "uint256",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256",
            },
        ],
        "name": "PortfolioUpdated",
        "type": "event",
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getPortfolio",
        "outputs": [
            {"internalType": "string[]", "name": "assets", "type": "string[]"},
            {"internalType": "uint256[]", "name": "allocations", "type": "uint256[]"},
            {"internalType": "uint256", "name": "updatedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "version", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "string[]", "name": "_assets", "type": "string[]"},
            {"internalType": "uint256[]", "name": "_allocations", "type": "uint256[]"},
        ],
        "name": "updatePortfolio",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Fallback ABI: mirrors RiskManagement.sol. calculateVolatility mutates
# state (it stores the result and emits an event), so it must be declared
# "nonpayable", not "view" as it was previously. web3.py's .call() still
# simulates it without sending a transaction either way, but a "view" tag
# here misrepresents the contract and would need correcting for anything
# that relies on ABI metadata (e.g. gas estimation, static analysis).
_RISK_MANAGEMENT_ABI_FALLBACK = [
    {
        "inputs": [
            {"internalType": "address", "name": "_priceFeed", "type": "address"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "lookbackDays", "type": "uint256"}
        ],
        "name": "calculateVolatility",
        "outputs": [
            {"internalType": "uint256", "name": "volatilityBps", "type": "uint256"}
        ],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "user", "type": "address"}],
        "name": "getLatestVolatility",
        "outputs": [
            {"internalType": "uint256", "name": "volatilityBps", "type": "uint256"},
            {"internalType": "uint256", "name": "observedAt", "type": "uint256"},
            {"internalType": "uint256", "name": "lookbackDays", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

# Fallback ABI: mirrors PortfolioLedger.sol. recordTransaction takes no
# _userAddress parameter (msg.sender is used - see the equivalent fix in
# web3_integration.py's MOCK_ABI); TransactionLogged's fields match the
# event exactly (transactionId, userAddress, transactionType, assetTicker,
# quantity, price).
_PORTFOLIO_LEDGER_ABI_FALLBACK = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "uint256",
                "name": "transactionId",
                "type": "uint256",
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "userAddress",
                "type": "address",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "transactionType",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "assetTicker",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "quantity",
                "type": "uint256",
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "price",
                "type": "uint256",
            },
        ],
        "name": "TransactionLogged",
        "type": "event",
    },
    {
        "inputs": [
            {"internalType": "string", "name": "_transactionType", "type": "string"},
            {"internalType": "string", "name": "_assetTicker", "type": "string"},
            {"internalType": "uint256", "name": "_quantity", "type": "uint256"},
            {"internalType": "uint256", "name": "_price", "type": "uint256"},
            {"internalType": "string", "name": "_notes", "type": "string"},
        ],
        "name": "recordTransaction",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getTransactionCount",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

PORTFOLIO_TRACKER_ABI = _load_abi(
    "PortfolioTracker", "PortfolioTracker", _PORTFOLIO_TRACKER_ABI_FALLBACK
)
RISK_MANAGEMENT_ABI = _load_abi(
    "RiskManagement", "RiskManagement", _RISK_MANAGEMENT_ABI_FALLBACK
)
PORTFOLIO_LEDGER_ABI = _load_abi(
    "PortfolioLedger", "PortfolioLedger", _PORTFOLIO_LEDGER_ABI_FALLBACK
)

DEFAULT_PORTFOLIO_TRACKER_ADDRESS = os.getenv(
    "PORTFOLIO_TRACKER_ADDRESS", "0x1234567890123456789012345678901234567890"
)
DEFAULT_RISK_MANAGEMENT_ADDRESS = os.getenv(
    "RISK_MANAGEMENT_ADDRESS", "0x0987654321098765432109876543210987654321"
)
DEFAULT_PORTFOLIO_LEDGER_ADDRESS = os.getenv(
    "PORTFOLIO_LEDGER_ADDRESS", "0x1111111111111111111111111111111111111111"
)

NETWORKS = {
    "local": {
        "name": "Local Development (Hardhat/Ganache)",
        "rpc_url": os.getenv("LOCAL_RPC_URL", "http://127.0.0.1:8545"),
        "chain_id": 31337,
        "explorer": "",
    },
    "ethereum": {
        "name": "Ethereum Mainnet",
        "rpc_url": os.getenv(
            "ETH_RPC_URL", "https://mainnet.infura.io/v3/your-infura-key"
        ),
        "chain_id": 1,
        "explorer": "https://etherscan.io",
    },
    "polygon": {
        "name": "Polygon Mainnet",
        "rpc_url": os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
        "chain_id": 137,
        "explorer": "https://polygonscan.com",
    },
    "arbitrum": {
        "name": "Arbitrum One",
        "rpc_url": os.getenv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
        "chain_id": 42161,
        "explorer": "https://arbiscan.io",
    },
    "optimism": {
        "name": "Optimism",
        "rpc_url": os.getenv("OPTIMISM_RPC_URL", "https://mainnet.optimism.io"),
        "chain_id": 10,
        "explorer": "https://optimistic.etherscan.io",
    },
    "goerli": {
        "name": "Goerli Testnet",
        "rpc_url": os.getenv(
            "GOERLI_RPC_URL", "https://goerli.infura.io/v3/your-infura-key"
        ),
        "chain_id": 5,
        "explorer": "https://goerli.etherscan.io",
    },
}

# The backend's central config (code/backend/src/core/config.py, populated
# from the single BLOCKCHAIN_PROVIDER env var documented in
# code/backend/.env.example) is the project's actual documented deployment
# target: whatever endpoint BLOCKCHAIN_PROVIDER points to. It previously had
# no effect on this module at all: BlockchainService only understood the
# named multi-chain NETWORKS above (via ETH_RPC_URL, POLYGON_RPC_URL, etc,
# none of which are mentioned in .env.example), and defaulted to
# "ethereum" regardless of what BLOCKCHAIN_PROVIDER was set to. A "custom"
# network entry backed directly by BLOCKCHAIN_PROVIDER closes that gap: it
# becomes the default whenever no specific named network is requested, so
# local development and single-endpoint deployments work out of the box
# from the documented env var alone, while named networks remain available
# for explicit multi-chain use (get_blockchain_service(network="polygon")).
NETWORKS["custom"] = {
    "name": "Custom (BLOCKCHAIN_PROVIDER)",
    "rpc_url": os.getenv("BLOCKCHAIN_PROVIDER", NETWORKS["local"]["rpc_url"]),
    "chain_id": None,
    "explorer": "",
}


def _get_raw_transaction(signed_tx: "np.ndarray | pd.DataFrame | list") -> bytes:
    """
    Extract raw transaction bytes from a signed transaction.
    Handles web3.py v5 (.rawTransaction) and v6+ (.raw_transaction).
    """
    if hasattr(signed_tx, "raw_transaction"):
        return signed_tx.raw_transaction
    if hasattr(signed_tx, "rawTransaction"):
        return signed_tx.rawTransaction
    raise AttributeError(
        "Signed transaction object has neither 'raw_transaction' nor 'rawTransaction'."
    )


class BlockchainService:
    """Service for blockchain integration and smart contract interaction."""

    def __init__(self, network: str = None) -> None:
        """
        Initialize the blockchain service.

        Args:
            network: Named network to connect to (e.g. "local", "ethereum",
                "polygon"). If omitted, resolves in order: the
                DEFAULT_BLOCKCHAIN_NETWORK env var, then the "custom"
                network backed by BLOCKCHAIN_PROVIDER (the single endpoint
                documented in .env.example), so the service works out of
                the box against whatever chain BLOCKCHAIN_PROVIDER points
                to without requiring a named network to be picked.
        """
        network = network or os.getenv("DEFAULT_BLOCKCHAIN_NETWORK") or "custom"
        self.network = network
        self.network_config = NETWORKS.get(network, NETWORKS["custom"])
        self.w3 = Web3(HTTPProvider(self.network_config["rpc_url"]))

        if ExtraDataToPOAMiddleware is not None:
            try:
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except Exception:
                self.w3.middleware_onion.add(ExtraDataToPOAMiddleware)

        # Guard against a None strategy: not every web3.py build exposes
        # medium_gas_price_strategy (removed/relocated across versions).
        if medium_gas_price_strategy is not None:
            self.w3.eth.set_gas_price_strategy(medium_gas_price_strategy)

        self.portfolio_tracker = self.w3.eth.contract(
            address=Web3.to_checksum_address(DEFAULT_PORTFOLIO_TRACKER_ADDRESS),
            abi=PORTFOLIO_TRACKER_ABI,
        )
        self.risk_management = self.w3.eth.contract(
            address=Web3.to_checksum_address(DEFAULT_RISK_MANAGEMENT_ADDRESS),
            abi=RISK_MANAGEMENT_ABI,
        )
        self.portfolio_ledger = self.w3.eth.contract(
            address=Web3.to_checksum_address(DEFAULT_PORTFOLIO_LEDGER_ADDRESS),
            abi=PORTFOLIO_LEDGER_ABI,
        )

        self.account = None
        private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
        if private_key:
            self.account = Account.from_key(private_key)

    def is_connected(self) -> bool:
        """Check if connected to blockchain network."""
        return self.w3.is_connected()

    def get_network_info(self) -> Dict[str, object]:
        """Get information about the connected network."""
        return {
            "name": self.network_config["name"],
            "chain_id": self.network_config["chain_id"],
            "connected": self.is_connected(),
            "latest_block": self.w3.eth.block_number if self.is_connected() else None,
            "gas_price": self.w3.eth.gas_price if self.is_connected() else None,
        }

    def validate_address(self, address: str) -> bool:
        """Validate Ethereum address format."""
        return self.w3.is_address(address)

    def get_portfolio(self, address: str) -> Dict[str, object]:
        """
        Get portfolio from blockchain.

        Args:
            address: User's Ethereum address

        Returns:
            Dictionary with portfolio data
        """
        if not self.validate_address(address):
            raise ValueError("Invalid Ethereum address")
        try:
            (
                assets,
                allocations,
                updated_at,
                version,
            ) = self.portfolio_tracker.functions.getPortfolio(
                Web3.to_checksum_address(address)
            ).call()
            allocations_pct = [allocation / 10000 for allocation in allocations]
            return {
                "user_address": address,
                "assets": assets,
                "allocations": allocations_pct,
                "updated_at": updated_at,
                "version": version,
                "source": "blockchain",
                "network": self.network_config["name"],
            }
        except Exception as e:
            logger.error(f"Error getting portfolio from blockchain: {e}")
            return None

    def update_portfolio(
        self, address: str, assets: list, allocations_pct: object
    ) -> Dict[str, object]:
        """
        Update portfolio on blockchain.

        Args:
            address: User's Ethereum address
            assets: List of asset symbols
            allocations_pct: List of allocation fractions (0.0-1.0, must sum
                to 1.0), the same convention returned by get_portfolio()'s
                "allocations" field, e.g. [0.5, 0.3, 0.2] for 50/30/20%.
                Converted to on-chain basis points (0-10000) internally.

        Returns:
            Transaction hash if successful, None otherwise
        """
        if not self.account:
            raise ValueError("Private key not configured for transaction signing")
        if not self.validate_address(address):
            raise ValueError("Invalid Ethereum address")
        if len(assets) != len(allocations_pct):
            raise ValueError("Assets and allocations must have the same length")

        allocations_bp = [int(round(pct * 10000)) for pct in allocations_pct]
        if abs(sum(allocations_bp) - 10000) > 10:
            raise ValueError("Allocations must sum to 100%")

        try:
            tx = self.portfolio_tracker.functions.updatePortfolio(
                assets, allocations_bp
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.w3.eth.get_transaction_count(self.account.address),
                    "gas": 2000000,
                    "gasPrice": self.w3.eth.gas_price,
                }
            )
            signed_tx = self.account.sign_transaction(tx)
            # web3.py renamed this attribute between v5 (rawTransaction) and
            # v6+ (raw_transaction); the helper handles both.
            raw_tx = _get_raw_transaction(signed_tx)
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return {
                "tx_hash": tx_hash.hex(),
                "status": "success" if receipt.status == 1 else "failed",
                "block_number": receipt.blockNumber,
                "gas_used": receipt.gasUsed,
                "explorer_url": f"{self.network_config['explorer']}/tx/{tx_hash.hex()}",
            }
        except Exception as e:
            logger.error(f"Error updating portfolio on blockchain: {e}")
            return None

    def calculate_volatility(self, lookback_days: object = 30) -> Dict[str, object]:
        """
        Calculate and persist volatility on-chain via the risk management
        contract.

        calculateVolatility is a state-changing contract function (it
        stores the result and emits an event - see RiskManagement.sol), so
        this sends and confirms a real transaction rather than only
        simulating it; a plain `.call()` here would return a value without
        ever writing it on-chain, silently defeating the point of a
        contract designed to persist a queryable volatility history.

        Args:
            lookback_days: Number of days to look back

        Returns:
            Transaction result dict (see update_portfolio), or None on
            failure.
        """
        if not self.account:
            raise ValueError("Private key not configured for transaction signing")
        try:
            tx = self.risk_management.functions.calculateVolatility(
                lookback_days
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.w3.eth.get_transaction_count(self.account.address),
                    "gas": 2000000,
                    "gasPrice": self.w3.eth.gas_price,
                }
            )
            signed_tx = self.account.sign_transaction(tx)
            raw_tx = _get_raw_transaction(signed_tx)
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return {
                "tx_hash": tx_hash.hex(),
                "status": "success" if receipt.status == 1 else "failed",
                "block_number": receipt.blockNumber,
                "gas_used": receipt.gasUsed,
                "explorer_url": f"{self.network_config['explorer']}/tx/{tx_hash.hex()}",
            }
        except Exception as e:
            logger.error(f"Error calculating volatility on blockchain: {e}")
            return None

    def get_latest_volatility(self, address: str) -> Dict[str, object]:
        """
        Read back the most recently stored volatility for an address
        (the result of a prior calculate_volatility() call).
        """
        if not self.validate_address(address):
            raise ValueError("Invalid Ethereum address")
        try:
            volatility_bps, observed_at, lookback_days = (
                self.risk_management.functions.getLatestVolatility(
                    Web3.to_checksum_address(address)
                ).call()
            )
            return {
                "user_address": address,
                "volatility_bps": volatility_bps,
                "observed_at": observed_at,
                "lookback_days": lookback_days,
            }
        except Exception as e:
            logger.error(f"Error reading volatility from blockchain: {e}")
            return None

    def get_transaction_history(
        self, address: str, limit: object = 10
    ) -> Dict[str, object]:
        """
        Get transaction history for an address.

        Args:
            address: User's Ethereum address
            limit: Maximum number of transactions to return

        Returns:
            List of transactions
        """
        if not self.validate_address(address):
            raise ValueError("Invalid Ethereum address")
        try:
            latest_block = self.w3.eth.block_number
            portfolio_filter = self.portfolio_tracker.events.PortfolioUpdated.create_filter(
                # web3.py v6+ renamed these to snake_case (from the
                # v5-era fromBlock/toBlock).
                from_block=max(latest_block - 10000, 0),
                to_block="latest",
                # PortfolioTracker.sol's event indexes its address
                # parameter as `user`, not `owner`.
                argument_filters={"user": Web3.to_checksum_address(address)},
            )
            events = portfolio_filter.get_all_entries()
            transactions = []
            for event in events[:limit]:
                block = self.w3.eth.get_block(event["blockNumber"])
                # gas actually consumed comes from the receipt, not the
                # transaction object (tx["gas"] is only the sender's gas
                # limit, which is typically higher than what was used).
                receipt = self.w3.eth.get_transaction_receipt(event["transactionHash"])
                transactions.append(
                    {
                        "tx_hash": event["transactionHash"].hex(),
                        "block_number": event["blockNumber"],
                        "timestamp": block["timestamp"],
                        "event": "PortfolioUpdated",
                        "gas_used": receipt["gasUsed"],
                        "explorer_url": f"{self.network_config['explorer']}/tx/{event['transactionHash'].hex()}",
                    }
                )
            return transactions
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []

    def record_ledger_transaction(
        self,
        transaction_type: str,
        asset_ticker: str,
        quantity: object,
        price: object,
        notes: str = "",
    ) -> Dict[str, object]:
        """
        Record an individual buy/sell/rebalance transaction on the
        immutable PortfolioLedger contract (distinct from
        update_portfolio(), which overwrites PortfolioTracker's current
        allocation snapshot - this appends a permanent log entry instead).

        The contract attributes the entry to msg.sender; there is no
        user_address parameter to pass (see PortfolioLedger.sol).

        Args:
            transaction_type: e.g. "BUY", "SELL", "REBALANCE"
            asset_ticker: Asset symbol, e.g. "BTC"
            quantity: Quantity traded (integer, caller's chosen unit scale)
            price: Price at time of transaction (integer, caller's chosen
                unit scale - PortfolioLedger stores this as-is, with no
                on-chain decimal convention of its own)
            notes: Optional free-text note

        Returns:
            Transaction result dict (see update_portfolio), or None on
            failure.
        """
        if not self.account:
            raise ValueError("Private key not configured for transaction signing")
        try:
            tx = self.portfolio_ledger.functions.recordTransaction(
                transaction_type, asset_ticker, int(quantity), int(price), notes
            ).build_transaction(
                {
                    "from": self.account.address,
                    "nonce": self.w3.eth.get_transaction_count(self.account.address),
                    "gas": 2000000,
                    "gasPrice": self.w3.eth.gas_price,
                }
            )
            signed_tx = self.account.sign_transaction(tx)
            raw_tx = _get_raw_transaction(signed_tx)
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return {
                "tx_hash": tx_hash.hex(),
                "status": "success" if receipt.status == 1 else "failed",
                "block_number": receipt.blockNumber,
                "gas_used": receipt.gasUsed,
                "explorer_url": f"{self.network_config['explorer']}/tx/{tx_hash.hex()}",
            }
        except Exception as e:
            logger.error(f"Error recording ledger transaction: {e}")
            return None

    def get_ledger_transactions(
        self, address: str, limit: object = 50
    ) -> Dict[str, object]:
        """
        Read an address's individual transaction log from the
        PortfolioLedger contract (TransactionLogged events), most recent
        first.

        Args:
            address: User's Ethereum address
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dicts: tx_hash, action (BUY/SELL/...),
            symbol, quantity, price, timestamp, status, block_number,
            explorer_url. Empty list on failure or if none found.
        """
        if not self.validate_address(address):
            raise ValueError("Invalid Ethereum address")
        try:
            latest_block = self.w3.eth.block_number
            ledger_filter = (
                self.portfolio_ledger.events.TransactionLogged.create_filter(
                    from_block=max(latest_block - 10000, 0),
                    to_block="latest",
                    argument_filters={"userAddress": Web3.to_checksum_address(address)},
                )
            )
            events = ledger_filter.get_all_entries()
            transactions = []
            # Most recent first, matching what a transaction history UI expects.
            for event in reversed(events[-limit:]):
                block = self.w3.eth.get_block(event["blockNumber"])
                transactions.append(
                    {
                        "tx_hash": event["transactionHash"].hex(),
                        "block_number": event["blockNumber"],
                        "timestamp": block["timestamp"],
                        "action": event["args"]["transactionType"],
                        "symbol": event["args"]["assetTicker"],
                        "quantity": event["args"]["quantity"],
                        "price": event["args"]["price"],
                        "status": "confirmed",
                        "explorer_url": f"{self.network_config['explorer']}/tx/{event['transactionHash'].hex()}",
                    }
                )
            return transactions
        except Exception as e:
            logger.error(f"Error getting ledger transactions: {e}")
            return []

    def get_gas_estimate(
        self, assets: list, allocations_pct: object
    ) -> Dict[str, object]:
        """
        Estimate gas for a portfolio update.

        Args:
            assets: List of asset symbols
            allocations_pct: List of allocation fractions (0.0-1.0), the
                same convention as update_portfolio()/get_portfolio(). Must
                use the identical values you intend to actually submit:
                estimate_gas simulates the real call, so a different
                conversion here would estimate gas for a different
                (possibly reverting) transaction than the one that gets sent.

        Returns:
            Estimated gas amount
        """
        if not self.account:
            raise ValueError("Private key not configured for transaction signing")
        allocations_bp = [int(round(pct * 10000)) for pct in allocations_pct]
        try:
            gas_estimate = self.portfolio_tracker.functions.updatePortfolio(
                assets, allocations_bp
            ).estimate_gas({"from": self.account.address})
            return gas_estimate
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            return None

    def switch_network(self, network: str) -> bool:
        """
        Switch to a different blockchain network.

        Args:
            network: Network name

        Returns:
            True if successful, False otherwise
        """
        if network not in NETWORKS:
            raise ValueError(f"Unsupported network: {network}")
        try:
            self.network = network
            self.network_config = NETWORKS[network]
            self.w3 = Web3(HTTPProvider(self.network_config["rpc_url"]))

            if ExtraDataToPOAMiddleware is not None:
                try:
                    self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
                except Exception:
                    self.w3.middleware_onion.add(ExtraDataToPOAMiddleware)

            # Guard against a None strategy, same as in __init__.
            if medium_gas_price_strategy is not None:
                self.w3.eth.set_gas_price_strategy(medium_gas_price_strategy)

            self.portfolio_tracker = self.w3.eth.contract(
                address=Web3.to_checksum_address(DEFAULT_PORTFOLIO_TRACKER_ADDRESS),
                abi=PORTFOLIO_TRACKER_ABI,
            )
            self.risk_management = self.w3.eth.contract(
                address=Web3.to_checksum_address(DEFAULT_RISK_MANAGEMENT_ADDRESS),
                abi=RISK_MANAGEMENT_ABI,
            )
            self.portfolio_ledger = self.w3.eth.contract(
                address=Web3.to_checksum_address(DEFAULT_PORTFOLIO_LEDGER_ADDRESS),
                abi=PORTFOLIO_LEDGER_ABI,
            )
            return self.is_connected()
        except Exception as e:
            logger.error(f"Error switching network: {e}")
            return False

    def get_supported_networks(self) -> Dict[str, object]:
        """Get list of supported blockchain networks."""
        return {
            network: {
                "name": config["name"],
                "chain_id": config["chain_id"],
                "explorer": config["explorer"],
            }
            for network, config in NETWORKS.items()
        }


def get_blockchain_service(network: str = None) -> BlockchainService:
    """
    Create a BlockchainService instance.

    Args:
        network: Named network (e.g. "local", "polygon"). If omitted,
            BlockchainService resolves DEFAULT_BLOCKCHAIN_NETWORK, then
            falls back to "custom" (BLOCKCHAIN_PROVIDER) - see
            BlockchainService.__init__.

    Constructed lazily (called by application code, not executed at import
    time) so an unreachable RPC endpoint doesn't crash module import.
    """
    return BlockchainService(network=network)
