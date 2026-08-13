// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title PortfolioLedger
 * @dev A simple smart contract to record and log portfolio transactions on-chain.
 *      It serves as an immutable ledger for all asset movements.
 */
contract PortfolioLedger {
    // Define the structure for a transaction log
    struct Transaction {
        uint256 timestamp;
        address userAddress; // The address of the user who initiated the transaction
        string transactionType; // e.g., "BUY", "SELL", "REBALANCE"
        string assetTicker;
        uint256 quantity;
        uint256 price; // Price at the time of the transaction
        string notes;
    }

    // Array to store all transactions
    Transaction[] public transactions;

    // Event to log when a new transaction is recorded
    /**
     * @dev Emitted when a new transaction is successfully recorded.
     * @param transactionId The index of the transaction in the `transactions` array.
     * @param userAddress The address of the user who initiated the transaction.
     * @param transactionType The type of the transaction (e.g., "BUY").
     * @param assetTicker The ticker symbol of the asset.
     * @param quantity The quantity of the asset involved.
     * @param price The price of the asset at the time of the transaction.
     */
    event TransactionLogged(
        uint256 indexed transactionId,
        address indexed userAddress,
        string transactionType,
        string assetTicker,
        uint256 quantity,
        uint256 price
    );

    /**
     * @dev Records a new transaction for the user who calls this function.
     *      The transaction is immutable once recorded.
     * @param _transactionType The type of the transaction (e.g., "BUY", "SELL").
     * @param _assetTicker The ticker symbol of the asset.
     * @param _quantity The quantity of the asset.
     * @param _price The price of the asset at the time of the transaction.
     * @param _notes Any additional notes for the transaction.
     */
    function recordTransaction(
        string memory _transactionType,
        string memory _assetTicker,
        uint256 _quantity,
        uint256 _price,
        string memory _notes
    ) public {
        // The user's address is derived from msg.sender, not passed as a parameter
        address user = msg.sender;

        // Add the new transaction to the array
        transactions.push(
            Transaction(
                block.timestamp,
                user,
                _transactionType,
                _assetTicker,
                _quantity,
                _price,
                _notes
            )
        );

        uint256 newTransactionId = transactions.length - 1;

        // Emit an event for easy off-chain indexing
        emit TransactionLogged(
            newTransactionId,
            user,
            _transactionType,
            _assetTicker,
            _quantity,
            _price
        );
    }

    /**
     * @dev Returns the total number of transactions recorded.
     * @return The total count of transactions.
     */
    function getTransactionCount() public view returns (uint256) {
        return transactions.length;
    }
}
