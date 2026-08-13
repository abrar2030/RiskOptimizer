# Local Hardhat node for development only (see docker-compose.override.yml).
# Not used in production: production points BLOCKCHAIN_PROVIDER at a real
# network instead of running a chain in-cluster.
#
# Build context is code/blockchain/ itself (not the repo root).
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY hardhat.config.js ./
COPY contracts/ ./contracts/
COPY scripts/ ./scripts/

RUN npx hardhat compile

EXPOSE 8545

# Runs an in-memory Hardhat node, then deploys the contracts to it so the
# backend has real addresses to talk to on startup (see scripts/deploy.js:
# on the "localhost" network it deploys a MockV3Aggregator automatically).
CMD ["sh", "-c", "npx hardhat node --hostname 0.0.0.0 & sleep 3 && npx hardhat run scripts/deploy.js --network localhost && wait"]
