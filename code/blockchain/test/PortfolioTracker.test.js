const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("PortfolioTracker", function () {
  let tracker;
  let owner;
  let user;
  let operator;
  let stranger;

  beforeEach(async function () {
    [owner, user, operator, stranger] = await ethers.getSigners();
    const PortfolioTracker =
      await ethers.getContractFactory("PortfolioTracker");
    tracker = await PortfolioTracker.deploy();
    await tracker.waitForDeployment();
  });

  it("updates the caller's own portfolio", async function () {
    const assets = ["BTC", "ETH"];
    const allocations = [5000, 5000];

    await tracker.connect(user).updatePortfolio(assets, allocations);

    const [storedAssets, storedAllocations, updatedAt, version] =
      await tracker.getPortfolio(user.address);

    expect(storedAssets).to.deep.equal(assets);
    expect(storedAllocations.map((a) => a.toString())).to.deep.equal(
      allocations.map(String),
    );
    expect(version).to.equal(1n);
    expect(updatedAt).to.be.greaterThan(0n);
  });

  it("reverts with InputLengthMismatch when assets/allocations lengths differ", async function () {
    await expect(
      tracker.connect(user).updatePortfolio(["BTC", "ETH"], [5000]),
    ).to.be.revertedWithCustomError(tracker, "InputLengthMismatch");
  });

  it("reverts with AllocationSumMismatch when allocations do not sum to 10000", async function () {
    await expect(
      tracker.connect(user).updatePortfolio(["BTC", "ETH"], [5000, 4000]),
    ).to.be.revertedWithCustomError(tracker, "AllocationSumMismatch");
  });

  it("reverts with EmptyAssetName for a blank asset symbol", async function () {
    await expect(
      tracker.connect(user).updatePortfolio(["", "ETH"], [5000, 5000]),
    ).to.be.revertedWithCustomError(tracker, "EmptyAssetName");
  });

  it("reverts with TooManyAssets beyond the configured maximum", async function () {
    const max = Number(await tracker.MAX_ASSETS());
    const assets = Array.from({ length: max + 1 }, (_, i) => `A${i}`);
    const allocations = assets.map((_, i) =>
      i === 0 ? 10000 - (assets.length - 1) : 1,
    );

    await expect(
      tracker.connect(user).updatePortfolio(assets, allocations),
    ).to.be.revertedWithCustomError(tracker, "TooManyAssets");
  });

  it("archives the previous allocation into history on update", async function () {
    await tracker.connect(user).updatePortfolio(["BTC", "ETH"], [5000, 5000]);
    await tracker
      .connect(user)
      .updatePortfolio(["BTC", "ETH", "SOL"], [4000, 4000, 2000]);

    expect(await tracker.historyLength(user.address)).to.equal(1n);

    const [histAssets, histAllocations] = await tracker.getHistoryEntry(
      user.address,
      0,
    );
    expect(histAssets).to.deep.equal(["BTC", "ETH"]);
    expect(histAllocations.map((a) => a.toString())).to.deep.equal([
      "5000",
      "5000",
    ]);
  });

  it("rejects operator updates from unauthorised addresses", async function () {
    await expect(
      tracker
        .connect(operator)
        .updatePortfolioFor(user.address, ["BTC"], [10000]),
    ).to.be.revertedWithCustomError(tracker, "Unauthorised");
  });

  it("allows an authorised operator to update on behalf of a user", async function () {
    await tracker.connect(owner).setOperator(operator.address, true);
    expect(await tracker.isOperator(operator.address)).to.equal(true);

    await tracker
      .connect(operator)
      .updatePortfolioFor(user.address, ["BTC"], [10000]);

    const [storedAssets] = await tracker.getPortfolio(user.address);
    expect(storedAssets).to.deep.equal(["BTC"]);
  });

  it("rejects setOperator from a non-owner", async function () {
    await expect(
      tracker.connect(stranger).setOperator(operator.address, true),
    ).to.be.revertedWithCustomError(tracker, "Unauthorised");
  });
});
