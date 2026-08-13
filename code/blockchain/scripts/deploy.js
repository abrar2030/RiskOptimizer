const { ethers, network } = require("hardhat");

/**
 * Deploys PortfolioLedger, PortfolioTracker, and RiskManagement.
 *
 * The previous Truffle migration hardcoded the mainnet ETH/USD Chainlink
 * feed address for every network, including local development, where no
 * such contract exists. This script:
 *   - deploys a MockV3Aggregator as the price feed on local/dev networks
 *     (hardhat, localhost) so RiskManagement can actually be exercised
 *     without a mainnet fork;
 *   - requires an explicit CHAINLINK_PRICE_FEED_ADDRESS env var on every
 *     other (live) network, defaulting to the mainnet ETH/USD feed only
 *     when network name is "mainnet".
 */

const MAINNET_ETH_USD_FEED = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419";
const LOCAL_NETWORKS = new Set(["hardhat", "localhost"]);

async function resolvePriceFeedAddress() {
  if (LOCAL_NETWORKS.has(network.name)) {
    const Mock = await ethers.getContractFactory("MockV3Aggregator");
    const mock = await Mock.deploy(8, 2000_00000000); // 8 decimals, $2000.00000000
    await mock.waitForDeployment();
    const address = await mock.getAddress();

    // Seed enough round history for calculateVolatility to work out of the
    // box in local dev (it requires at least 2, up to 30, rounds - see
    // RiskManagement.sol's MIN/MAX_LOOKBACK_DAYS). A real Chainlink feed
    // always has deep history; a freshly deployed mock with only its
    // constructor round does not, and calculateVolatility would revert
    // with InsufficientHistory/InvalidPrice until enough rounds exist.
    let price = 2000_00000000;
    for (let i = 0; i < 34; i++) {
      price += (i % 2 === 0 ? 1 : -1) * (5 + (i % 7)) * 1_00000000;
      await mock.updateAnswer(price);
    }

    console.log(`Deployed MockV3Aggregator (dev price feed) at ${address}`);
    console.log("  seeded with 35 rounds of price history");
    return address;
  }

  if (process.env.CHAINLINK_PRICE_FEED_ADDRESS) {
    return process.env.CHAINLINK_PRICE_FEED_ADDRESS;
  }

  if (network.name === "mainnet") {
    return MAINNET_ETH_USD_FEED;
  }

  throw new Error(
    `No CHAINLINK_PRICE_FEED_ADDRESS set for network "${network.name}". ` +
      "Set this env var to the correct feed address for the target network " +
      "before deploying RiskManagement.",
  );
}

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying contracts with account: ${deployer.address}`);
  console.log(`Network: ${network.name}`);

  const PortfolioLedger = await ethers.getContractFactory("PortfolioLedger");
  const ledger = await PortfolioLedger.deploy();
  await ledger.waitForDeployment();
  console.log(`PortfolioLedger deployed to: ${await ledger.getAddress()}`);

  const PortfolioTracker = await ethers.getContractFactory("PortfolioTracker");
  const tracker = await PortfolioTracker.deploy();
  await tracker.waitForDeployment();
  console.log(`PortfolioTracker deployed to: ${await tracker.getAddress()}`);

  const priceFeedAddress = await resolvePriceFeedAddress();
  const RiskManagement = await ethers.getContractFactory("RiskManagement");
  const risk = await RiskManagement.deploy(priceFeedAddress);
  await risk.waitForDeployment();
  console.log(`RiskManagement deployed to: ${await risk.getAddress()}`);
  console.log(`  using price feed: ${priceFeedAddress}`);

  return {
    portfolioLedger: await ledger.getAddress(),
    portfolioTracker: await tracker.getAddress(),
    riskManagement: await risk.getAddress(),
    priceFeed: priceFeedAddress,
  };
}

main()
  .then((addresses) => {
    console.log("\nDeployment summary:");
    console.log(JSON.stringify(addresses, null, 2));
    process.exit(0);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
