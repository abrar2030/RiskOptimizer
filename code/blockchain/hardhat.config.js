require("@nomicfoundation/hardhat-toolbox");

/**
 * Hardhat configuration for the RiskOptimizer smart contracts.
 *
 * Truffle was replaced with Hardhat because the previous truffle-config.js
 * could not compile the contracts in this project at all:
 *   - it pinned solc to 0.8.0 while every contract's pragma requires
 *     ^0.8.20 (custom errors, unchecked loops), so `truffle compile` would
 *     fail outright;
 *   - it declared a "solana" network for an EVM-only tool (Truffle cannot
 *     deploy to Solana, which is not EVM-compatible) and referenced
 *     HDWalletProvider without requiring the package;
 *   - Truffle itself has been unmaintained since ConsenSys sunset it in
 *     2023. Hardhat is the actively maintained standard toolchain.
 *
 * Network private keys and RPC URLs are read from environment variables so
 * no secrets are ever committed to the repository.
 */

const SEPOLIA_RPC_URL = process.env.SEPOLIA_RPC_URL || "";
const MAINNET_RPC_URL = process.env.MAINNET_RPC_URL || "";
const DEPLOYER_PRIVATE_KEY = process.env.DEPLOYER_PRIVATE_KEY;

const networks = {
  hardhat: {},
};

// Only register live networks when the required configuration is actually
// present, so `npx hardhat compile` / `npx hardhat test` never fail just
// because a .env file hasn't been set up.
if (SEPOLIA_RPC_URL && DEPLOYER_PRIVATE_KEY) {
  networks.sepolia = {
    url: SEPOLIA_RPC_URL,
    accounts: [DEPLOYER_PRIVATE_KEY],
    chainId: 11155111,
  };
}

if (MAINNET_RPC_URL && DEPLOYER_PRIVATE_KEY) {
  networks.mainnet = {
    url: MAINNET_RPC_URL,
    accounts: [DEPLOYER_PRIVATE_KEY],
    chainId: 1,
  };
}

module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: { enabled: true, runs: 200 },
      // Required: PortfolioTracker copies calldata arrays of strings (a
      // nested dynamic type) directly into storage, which the legacy
      // Solidity codegen cannot compile ("Copying nested calldata dynamic
      // arrays to storage is not implemented in the old code generator").
      viaIR: true,
    },
  },
  networks,
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
