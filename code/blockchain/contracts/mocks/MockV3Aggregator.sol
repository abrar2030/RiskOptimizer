// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title  MockV3Aggregator
/// @notice Minimal test double for a Chainlink `AggregatorV3Interface` price
///         feed. Lets tests push arbitrary rounds of price data so
///         RiskManagement.calculateVolatility can be exercised on a local
///         network without needing a mainnet fork.
contract MockV3Aggregator {
    uint8 public immutable decimals;
    uint80 private _latestRoundId;

    mapping(uint80 => int256) private _answers;
    mapping(uint80 => uint256) private _timestamps;

    constructor(uint8 _decimals, int256 _initialAnswer) {
        decimals = _decimals;
        _pushRound(_initialAnswer);
    }

    /// @notice Push a new round with the given answer, timestamped "now".
    function updateAnswer(int256 _answer) external {
        _pushRound(_answer);
    }

    /// @notice Push a new round with an explicit timestamp (for staleness tests).
    function updateAnswerAt(int256 _answer, uint256 _timestamp) external {
        _latestRoundId += 1;
        _answers[_latestRoundId] = _answer;
        _timestamps[_latestRoundId] = _timestamp;
    }

    function _pushRound(int256 _answer) internal {
        _latestRoundId += 1;
        _answers[_latestRoundId] = _answer;
        _timestamps[_latestRoundId] = block.timestamp;
    }

    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        return (
            _latestRoundId,
            _answers[_latestRoundId],
            _timestamps[_latestRoundId],
            _timestamps[_latestRoundId],
            _latestRoundId
        );
    }

    function getRoundData(
        uint80 _roundId
    )
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        return (
            _roundId,
            _answers[_roundId],
            _timestamps[_roundId],
            _timestamps[_roundId],
            _roundId
        );
    }
}
