const { expect } = require("chai");
const { ethers } = require("hardhat");

async function deployFeedWithRounds(prices, decimals = 8) {
  const Mock = await ethers.getContractFactory("MockV3Aggregator");
  const feed = await Mock.deploy(decimals, prices[0]);
  await feed.waitForDeployment();
  for (let i = 1; i < prices.length; i++) {
    await feed.updateAnswer(prices[i]);
  }
  return feed;
}

describe("RiskManagement", function () {
  let user;

  beforeEach(async function () {
    [user] = await ethers.getSigners();
  });

  it("reverts deployment with the zero address as price feed", async function () {
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    await expect(RiskManagement.deploy(ethers.ZeroAddress)).to.be.reverted;
  });

  it("stores and returns risk parameters", async function () {
    const feed = await deployFeedWithRounds([2000_00000000, 2010_00000000]);
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await risk.connect(user).setRiskParams(500, 2000, 3000);
    const [maxVarBps, maxDrawdownBps, maxConcentrationBps, active] =
      await risk.getRiskParams(user.address);

    expect(maxVarBps).to.equal(500n);
    expect(maxDrawdownBps).to.equal(2000n);
    expect(maxConcentrationBps).to.equal(3000n);
    expect(active).to.equal(true);
  });

  it("rejects out-of-range risk parameters", async function () {
    const feed = await deployFeedWithRounds([2000_00000000, 2010_00000000]);
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await expect(
      risk.connect(user).setRiskParams(0, 2000, 3000),
    ).to.be.revertedWithCustomError(risk, "InvalidParams");
    await expect(
      risk.connect(user).setRiskParams(500, 11000, 3000),
    ).to.be.revertedWithCustomError(risk, "InvalidParams");
  });

  it("emits RiskLimitBreached when the checked VaR exceeds the limit", async function () {
    const feed = await deployFeedWithRounds([2000_00000000, 2010_00000000]);
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await risk.connect(user).setRiskParams(500, 2000, 3000);

    await expect(risk.connect(user).checkVarLimit(200)).to.not.emit(
      risk,
      "RiskLimitBreached",
    );

    await expect(risk.connect(user).checkVarLimit(900))
      .to.emit(risk, "RiskLimitBreached")
      .withArgs(user.address, "VaR", 900n, 500n);
  });

  it("calculates non-zero volatility from a falling price series", async function () {
    // Prices trending steadily downward, oldest to newest. Before the fix,
    // calculateVolatility only accounted for days where price rose
    // ("newer >= older"); on a purely falling series every daily return
    // was floored to zero, so the reported volatility was always exactly
    // 0 regardless of how much the price actually moved. The fix uses the
    // absolute daily price change, so a falling series now yields a
    // correctly non-zero volatility.
    const chronologicalPrices = [
      2500_00000000, 2410_00000000, 2380_00000000, 2255_00000000, 2200_00000000,
      2130_00000000, 2050_00000000, 1980_00000000, 1930_00000000, 1850_00000000,
    ];
    const feed = await deployFeedWithRounds(chronologicalPrices);
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await risk.connect(user).calculateVolatility(10);
    const [volatilityBps, observedAt, lookbackDays] =
      await risk.getLatestVolatility(user.address);

    expect(volatilityBps).to.be.greaterThan(0n);
    expect(lookbackDays).to.equal(10n);
    expect(observedAt).to.be.greaterThan(0n);
  });

  it("reverts with InsufficientHistory outside the 2-30 day lookback range", async function () {
    const feed = await deployFeedWithRounds([2000_00000000, 2010_00000000]);
    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await expect(
      risk.connect(user).calculateVolatility(1),
    ).to.be.revertedWithCustomError(risk, "InsufficientHistory");
    await expect(
      risk.connect(user).calculateVolatility(31),
    ).to.be.revertedWithCustomError(risk, "InsufficientHistory");
  });

  it("reverts with StalePrice when the latest round is too old", async function () {
    const Mock = await ethers.getContractFactory("MockV3Aggregator");
    const feed = await Mock.deploy(8, 2000_00000000);
    await feed.waitForDeployment();

    // Push a stale round: timestamped far in the past.
    await feed.updateAnswerAt(2005_00000000, 1);

    const RiskManagement = await ethers.getContractFactory("RiskManagement");
    const risk = await RiskManagement.deploy(await feed.getAddress());
    await risk.waitForDeployment();

    await expect(
      risk.connect(user).calculateVolatility(2),
    ).to.be.revertedWithCustomError(risk, "StalePrice");
  });
});
