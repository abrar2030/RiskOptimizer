"""
RiskOptimizer blockchain package.

Contains the Solidity smart contracts (contracts/), Hardhat tooling
(hardhat.config.js, scripts/, test/), and the Python integration layer
(services/blockchain_service.py, web3_integration.py) used to read and
write on-chain portfolio and risk data.

This __init__.py makes the package explicit rather than relying on
Python's implicit namespace package resolution, matching every other
top-level package in code/ (backend, quant_ml).
"""
