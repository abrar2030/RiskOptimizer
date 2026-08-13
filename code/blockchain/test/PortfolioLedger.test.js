const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("PortfolioLedger", function () {
  let ledger;
  let owner;
  let other;

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();
    const PortfolioLedger = await ethers.getContractFactory("PortfolioLedger");
    ledger = await PortfolioLedger.deploy();
    await ledger.waitForDeployment();
  });

  it("starts with zero recorded transactions", async function () {
    expect(await ledger.getTransactionCount()).to.equal(0n);
  });

  it("records a transaction under the caller's own address", async function () {
    await expect(
      ledger
        .connect(other)
        .recordTransaction("BUY", "BTC", 2, 65_000, "initial buy"),
    )
      .to.emit(ledger, "TransactionLogged")
      .withArgs(0n, other.address, "BUY", "BTC", 2n, 65_000n);

    expect(await ledger.getTransactionCount()).to.equal(1n);

    const stored = await ledger.transactions(0);
    expect(stored.userAddress).to.equal(other.address);
    expect(stored.transactionType).to.equal("BUY");
    expect(stored.assetTicker).to.equal("BTC");
    expect(stored.quantity).to.equal(2n);
    expect(stored.price).to.equal(65_000n);
    expect(stored.notes).to.equal("initial buy");
  });

  it("increments the transaction id across multiple records", async function () {
    await ledger.recordTransaction("BUY", "ETH", 5, 3_000, "");
    await ledger.recordTransaction("SELL", "ETH", 2, 3_100, "");

    expect(await ledger.getTransactionCount()).to.equal(2n);
    const second = await ledger.transactions(1);
    expect(second.transactionType).to.equal("SELL");
  });
});
