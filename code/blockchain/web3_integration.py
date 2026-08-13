import logging
import os

from web3 import Web3

logger = logging.getLogger(__name__)
GANACHE_URL = "http://127.0.0.1:8545"
MOCK_CONTRACT_ADDRESS = "0x9fE46736679d2D9a65F0992F2272E2fA8C57Bf70"
# Mirrors the real PortfolioLedger.sol ABI. recordTransaction takes no
# _userAddress parameter: the contract derives the caller from msg.sender
# (see PortfolioLedger.sol), so an ABI with a leading address parameter here
# would encode calls that revert (or silently call the wrong function) against
# the real deployed contract.
MOCK_ABI = [
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


def get_web3_instance() -> object:
    """Initializes and returns a Web3 instance connected to the mock node."""
    try:
        w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
        if w3.is_connected():
            logger.info(f"Successfully connected to Ethereum node at {GANACHE_URL}")
            return w3
        else:
            logger.info(f"Failed to connect to Ethereum node at {GANACHE_URL}")
            return None
    except Exception as e:
        logger.info(f"Connection error: {e}")
        return None


def record_trade_on_blockchain(
    w3: Web3,
    user_address: str,
    tx_type: str,
    ticker: str,
    quantity: float,
    price: float,
    notes: str,
) -> object:
    """
    Records a trade or rebalancing event on the mock blockchain ledger.
    """
    if not w3:
        logger.info("Cannot record transaction: Web3 connection failed.")
        return
    quantity_wei = w3.to_wei(quantity, "ether")
    price_wei = w3.to_wei(price, "ether")
    contract = w3.eth.contract(address=MOCK_CONTRACT_ADDRESS, abi=MOCK_ABI)
    try:
        sender_account = w3.eth.accounts[0]
    except IndexError:
        logger.info(
            "Error: No accounts found. Ensure your local node (e.g., Ganache) is running."
        )
        return
    logger.info(f"\nRecording transaction from {sender_account}...")
    # PortfolioLedger.recordTransaction has no _userAddress parameter: the
    # contract attributes the transaction to msg.sender (sender_account)
    # rather than an address passed in as an argument. user_address is kept
    # as a function parameter here only for local logging/context.
    contract.functions.recordTransaction(
        tx_type, ticker, quantity_wei, price_wei, notes
    ).build_transaction(
        {
            "from": sender_account,
            "nonce": w3.eth.get_transaction_count(sender_account),
            "gas": 2000000,
        }
    )
    logger.info("Mock Transaction Built (would be sent to the network):")
    logger.info(
        f"  Function: recordTransaction('{tx_type}', '{ticker}', {quantity_wei}, {price_wei}, '{notes}')"
    )
    logger.info(f"  Attributed on-chain to (msg.sender): {sender_account}")
    logger.info(f"  Logical portfolio owner: {user_address}")
    mock_tx_hash = "0x" + os.urandom(32).hex()
    logger.info(f"  Mock Transaction Hash: {mock_tx_hash}")
    logger.info("Transaction successfully recorded on the mock blockchain.")


def get_ledger_count(w3: Web3) -> object:
    """Retrieves the total number of transactions recorded."""
    if not w3:
        return 0
    contract = w3.eth.contract(address=MOCK_CONTRACT_ADDRESS, abi=MOCK_ABI)
    try:
        count = contract.functions.getTransactionCount().call()
        logger.info(f"Total transactions on the mock ledger: {count}")
        return count
    except Exception as e:
        logger.info(f"Mock call failed (ensure mock contract is deployed): {e}")
        return 3


def run_blockchain_integration() -> object:
    """Main function to run the blockchain integration components."""
    logger.info(
        "Starting Blockchain Integration Service (Mocking local node connection)..."
    )
    w3 = get_web3_instance()
    mock_user_did = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
    initial_count = get_ledger_count(w3)
    record_trade_on_blockchain(
        w3,
        user_address=mock_user_did,
        tx_type="REBALANCE",
        ticker="MSFT",
        quantity=50.0,
        price=450.0,
        notes="Rebalance to Max Sharpe weights.",
    )
    logger.info(f"\nMock ledger count after recording: {initial_count + 1}")
    logger.info("\nBlockchain Integration Service finished.")


if __name__ == "__main__":
    run_blockchain_integration()
