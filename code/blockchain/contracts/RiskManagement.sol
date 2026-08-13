// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Minimal interface for Chainlink v3 price feeds.
interface AggregatorV3Interface {
    function latestRoundData()
        external
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        );

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
        );

    function decimals() external view returns (uint8);
}

/// @title  RiskManagement
/// @notice On-chain risk parameter registry and basic volatility estimation
///         using Chainlink price feeds. Stores user-defined risk limits and
///         emits alerts when breaches are detected.
contract RiskManagement {
    // ─── Structs ────────────────────────────────────────────────────────────

    struct RiskParams {
        uint256 maxVarBps; // max VaR in basis points (e.g. 500 = 5 %)
        uint256 maxDrawdownBps; // max drawdown in basis points
        uint256 maxConcentrationBps; // max single-asset weight in basis points
        bool active;
    }

    struct VolatilityResult {
        uint256 volatilityBps; // annualised vol in basis points
        uint256 observedAt; // block.timestamp of calculation
        uint256 lookbackDays;
    }

    // ─── State ──────────────────────────────────────────────────────────────

    AggregatorV3Interface public immutable priceFeed;
    address public immutable owner;

    mapping(address => RiskParams) private _riskParams;
    mapping(address => VolatilityResult) private _latestVolatility;

    // ─── Events ─────────────────────────────────────────────────────────────

    event RiskParamsUpdated(
        address indexed user,
        uint256 maxVarBps,
        uint256 maxDrawdownBps
    );
    event RiskLimitBreached(
        address indexed user,
        string limitType,
        uint256 actual,
        uint256 limit
    );
    event VolatilityCalculated(
        address indexed user,
        uint256 volatilityBps,
        uint256 lookbackDays
    );

    // ─── Errors ─────────────────────────────────────────────────────────────

    error Unauthorised();
    error InvalidParams();
    error StalePrice(uint256 age);
    error InvalidPrice(uint256 roundIndex);
    error InsufficientHistory(uint256 available, uint256 required);

    // ─── Constants ───────────────────────────────────────────────────────────

    uint256 public constant BASIS_POINTS = 10_000;
    uint256 public constant MAX_PRICE_AGE = 3600; // 1 hour staleness threshold
    uint256 public constant TRADING_DAYS_PER_YEAR = 252;

    // ─── Constructor ─────────────────────────────────────────────────────────

    constructor(address _priceFeed) {
        if (_priceFeed == address(0)) revert InvalidParams();
        priceFeed = AggregatorV3Interface(_priceFeed);
        owner = msg.sender;
    }

    // ─── External ────────────────────────────────────────────────────────────

    /// @notice Register or update risk parameters for the caller.
    function setRiskParams(
        uint256 maxVarBps,
        uint256 maxDrawdownBps,
        uint256 maxConcentrationBps
    ) external {
        if (maxVarBps == 0 || maxVarBps > BASIS_POINTS) revert InvalidParams();
        if (maxDrawdownBps == 0 || maxDrawdownBps > BASIS_POINTS)
            revert InvalidParams();
        if (maxConcentrationBps == 0 || maxConcentrationBps > BASIS_POINTS)
            revert InvalidParams();

        _riskParams[msg.sender] = RiskParams({
            maxVarBps: maxVarBps,
            maxDrawdownBps: maxDrawdownBps,
            maxConcentrationBps: maxConcentrationBps,
            active: true
        });

        emit RiskParamsUpdated(msg.sender, maxVarBps, maxDrawdownBps);
    }

    /// @notice Return the risk parameters for a given user.
    function getRiskParams(
        address user
    )
        external
        view
        returns (
            uint256 maxVarBps,
            uint256 maxDrawdownBps,
            uint256 maxConcentrationBps,
            bool active
        )
    {
        RiskParams storage p = _riskParams[user];
        return (p.maxVarBps, p.maxDrawdownBps, p.maxConcentrationBps, p.active);
    }

    /// @notice Check whether a given VaR (in bps) breaches the caller's limit.
    ///         Emits ``RiskLimitBreached`` if so.
    /// @param varBps Actual portfolio VaR in basis points.
    function checkVarLimit(uint256 varBps) external returns (bool breached) {
        RiskParams storage p = _riskParams[msg.sender];
        if (!p.active) return false;
        if (varBps > p.maxVarBps) {
            emit RiskLimitBreached(msg.sender, "VaR", varBps, p.maxVarBps);
            return true;
        }
        return false;
    }

    /// @notice Estimate realised volatility over ``lookbackDays`` using
    ///         on-chain Chainlink price history.
    ///         Returns annualised volatility in basis points.
    /// @param lookbackDays Number of daily observations to use (max 30).
    function calculateVolatility(
        uint256 lookbackDays
    ) external returns (uint256 volatilityBps) {
        if (lookbackDays < 2 || lookbackDays > 30)
            revert InsufficientHistory(lookbackDays, 2);

        // Fetch latest round
        (uint80 latestRoundId, , , uint256 updatedAt, ) = priceFeed
            .latestRoundData();
        if (block.timestamp - updatedAt > MAX_PRICE_AGE)
            revert StalePrice(block.timestamp - updatedAt);

        // Note: no explicit decimal-scale normalisation is needed here.
        // calculateVolatility works on ratios of consecutive prices
        // (diff / prices[i+1]), so the feed's fixed decimal precision
        // cancels out; only self-consistency across rounds matters.

        // Collect prices (one per simulated day, stepping back one round at a time)
        uint256[] memory prices = new uint256[](lookbackDays);
        for (uint256 i; i < lookbackDays; ++i) {
            uint80 roundId = uint80(uint256(latestRoundId) - i);
            (, int256 price, , , ) = priceFeed.getRoundData(roundId);
            if (price <= 0) revert InvalidPrice(i);
            prices[i] = uint256(price);
        }

        // Compute absolute log-returns × 10 000 (scaled integers to avoid floats)
        // Approximation: |log(p_t / p_{t-1})| ≈ |p_t - p_{t-1}| / p_{t-1}
        // Both upward and downward moves must contribute to the return series,
        // otherwise volatility is systematically understated during uptrends.
        uint256[] memory returns_ = new uint256[](lookbackDays - 1);
        uint256 mean;
        for (uint256 i; i < lookbackDays - 1; ++i) {
            uint256 diff =
                prices[i] >= prices[i + 1]
                    ? prices[i] - prices[i + 1]
                    : prices[i + 1] - prices[i];
            uint256 ret = (diff * BASIS_POINTS) / prices[i + 1];
            returns_[i] = ret;
            mean += ret;
        }
        mean /= (lookbackDays - 1);

        // Variance
        uint256 variance;
        for (uint256 i; i < returns_.length; ++i) {
            uint256 diff =
                returns_[i] > mean ? returns_[i] - mean : mean - returns_[i];
            variance += diff * diff;
        }
        variance /= returns_.length;

        // Annualise: vol = sqrt(variance * 252)
        uint256 annualisedVariance = variance * TRADING_DAYS_PER_YEAR;
        volatilityBps = _sqrt(annualisedVariance);

        // Store and emit
        _latestVolatility[msg.sender] = VolatilityResult({
            volatilityBps: volatilityBps,
            observedAt: block.timestamp,
            lookbackDays: lookbackDays
        });

        emit VolatilityCalculated(msg.sender, volatilityBps, lookbackDays);
        return volatilityBps;
    }

    /// @notice Return the most recently calculated volatility for a user.
    function getLatestVolatility(
        address user
    )
        external
        view
        returns (
            uint256 volatilityBps,
            uint256 observedAt,
            uint256 lookbackDays
        )
    {
        VolatilityResult storage v = _latestVolatility[user];
        return (v.volatilityBps, v.observedAt, v.lookbackDays);
    }

    // ─── Internal ────────────────────────────────────────────────────────────

    /// @dev Integer square root using the Babylonian method.
    function _sqrt(uint256 x) internal pure returns (uint256 z) {
        if (x == 0) return 0;
        z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }
}
