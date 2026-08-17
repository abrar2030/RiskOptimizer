# RiskOptimizer

![CI/CD Status](https://img.shields.io/github/actions/workflow/status/quantsingularity/RiskOptimizer/cicd.yml?branch=main&label=CI%2FCD&logo=github)

## AI-Powered Portfolio Risk Management Platform

RiskOptimizer is a portfolio risk management platform: a Flask backend for auth, portfolios, risk, and monitoring, paired with a React web dashboard and a React Native (Expo) mobile app. A quantitative library (`code/quant_ml`) provides VaR, extreme value theory, portfolio optimization, and forecasting, backed by a genuine Solidity ledger for recording portfolio changes on-chain.

<div align="center">
  <img src="docs/images/homepage.bmp" alt="RiskOptimizer HomePage" width="100%">
</div>

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Feature Status](#feature-status)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Installation and Setup](#installation-and-setup)
- [Running the Stack](#running-the-stack)
- [API Surface](#api-surface)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Overview

RiskOptimizer demonstrates a portfolio risk workflow across a real, runnable codebase. The application tier (backend, smart contracts, and two clients) is wired and covered by tests. The quantitative library covers VaR (historical, parametric, and Monte Carlo), extreme value theory, GARCH volatility, Prophet-based forecasting, portfolio optimization (PyPortfolioOpt), and lexicon-based sentiment analysis (NLTK's VADER), all built on scikit-learn and statistics rather than deep learning.

## Project Structure

```
RiskOptimizer/
├── code/
│   ├── backend/                  # Flask service: API, auth, services, DB, tasks
│   │   ├── src/api/controllers/  # auth, portfolio, risk, blockchain, monitoring
│   │   ├── src/domain/services/  # auth, portfolio, risk, audit services
│   │   ├── src/infrastructure/   # database, cache, repositories
│   │   ├── src/services/         # blockchain_service, quant_analysis, ai_optimization
│   │   ├── src/tasks/            # Celery background tasks
│   │   └── tests/                # Backend test suite (unit and integration)
│   ├── blockchain/               # Hardhat project
│   │   ├── contracts/            # PortfolioLedger, PortfolioTracker, RiskManagement
│   │   └── test/                 # Hardhat test suite
│   └── quant_ml/
│       ├── risk_engine/          # Parallel Monte Carlo (joblib + multiprocessing)
│       ├── risk_models/          # VaR, extreme value theory, GARCH, MLP regressor
│       ├── ai_models/            # PyPortfolioOpt optimization, Prophet + VADER sentiment
│       └── tests/                # quant_ml test suite
├── web-frontend/                 # React (Vite) dashboard
├── mobile-frontend/              # React Native + Expo app
├── infrastructure/               # Docker, Kubernetes, Terraform, Ansible, monitoring
├── scripts/                      # Setup, run, test, and deploy scripts
├── docs/                         # Documentation (this directory)
└── README.md
```

## Feature Status

### Application tier (wired and tested)

| Component                     | Details                                                                                                                                                                                                                                                                            |
| :---------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **API**                       | Flask backend exposing endpoints under `/api/v1` for auth, portfolios, risk, blockchain, and monitoring, plus Celery-backed background tasks for reports and maintenance.                                                                                                          |
| **Auth**                      | JWT sessions (PyJWT) with bcrypt password hashing. `SECRET_KEY`, `JWT_SECRET_KEY`, and `DATA_ENCRYPTION_KEY` are required environment variables in production; the app raises on startup if they're missing there.                                                                 |
| **Risk calculations**         | VaR (historical, parametric, and Monte Carlo), CVaR, Sharpe ratio, max drawdown, and an efficient frontier, computed in the domain and quant_ml layers.                                                                                                                            |
| **Parallel risk engine**      | A Monte Carlo engine that distributes simulation batches across CPU cores with joblib and multiprocessing.                                                                                                                                                                         |
| **Portfolio optimization**    | PyPortfolioOpt-based allocation, plus a scikit-learn `MLPRegressor` used as a lightweight risk model.                                                                                                                                                                              |
| **Forecasting and sentiment** | Prophet for price forecasting and NLTK's VADER lexicon analyzer for sentiment, both genuinely wired into `quant_ml/ai_models`.                                                                                                                                                     |
| **Smart contracts**           | Hardhat-managed Solidity contracts: `PortfolioLedger` and `PortfolioTracker` for recording portfolio state on-chain, and a `RiskManagement` contract, read and written via web3.py in `blockchain_service.py`.                                                                     |
| **Web dashboard**             | React app (JavaScript, not TypeScript) with Material-UI components, Recharts for charts, and React Query for data fetching, covering Home, Dashboard, Portfolio Management, Portfolio Optimization, Risk Analysis, Optimization, Monitoring, Settings, and authentication screens. |
| **Mobile app**                | React Native (Expo) app covering the same functional areas through React Navigation, with React Context (not Redux) for auth and theme state.                                                                                                                                      |

## Technology Stack

| Area             | Technology                                                                                                             |
| :--------------- | :--------------------------------------------------------------------------------------------------------------------- |
| Backend API      | Python 3.11+, Flask, Gunicorn, Flasgger (Swagger docs)                                                                 |
| Auth             | PyJWT, bcrypt, passlib                                                                                                 |
| Data layer       | SQLAlchemy 2, Alembic, PostgreSQL, Redis                                                                               |
| Background tasks | Celery                                                                                                                 |
| Quant / ML       | scikit-learn (MLPRegressor), statsmodels, arch (GARCH), Prophet, PyPortfolioOpt, NLTK (VADER sentiment)                |
| Blockchain       | Solidity, Hardhat, web3.py, eth-account                                                                                |
| Web frontend     | React 18, JavaScript, Vite, Material-UI, Recharts, React Query, Tailwind CSS                                           |
| Mobile frontend  | React Native, Expo, React Navigation, React Context                                                                    |
| Infrastructure   | Docker, Docker Compose, Kubernetes, Terraform, Ansible                                                                 |
| Monitoring       | Prometheus, Grafana, prometheus-client, structlog                                                                      |
| CI/CD            | GitHub Actions                                                                                                         |
| Testing          | pytest (backend), Hardhat (contracts); quant_ml and mobile have their own test suites, though neither runs in CI today |

## Architecture

```
Clients
  ├── web-frontend (React)               ── HTTP/JSON ──┐
  └── mobile-frontend (React Native)     ── HTTP/JSON ──┤
                                                        ▼
Backend (Flask, /api/v1)
  ├── Controllers  auth, portfolio, risk, blockchain, monitoring
  ├── Domain       auth, portfolio, risk, audit services
  ├── Tasks        Celery background jobs (reports, maintenance, risk, portfolio)
  ├── Services      blockchain_service (web3.py), quant_analysis, ai_optimization
  └── Data layer     PostgreSQL (SQLAlchemy + Alembic), Redis

Blockchain (Hardhat / Solidity)
  PortfolioLedger · PortfolioTracker · RiskManagement

Quant library (code/quant_ml)
  risk_engine (parallel Monte Carlo) · risk_models (VaR, EVT, GARCH, MLP)
  ai_models (PyPortfolioOpt, Prophet, VADER sentiment)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detail.

## Installation and Setup

Prerequisites: Python 3.11+ and Node.js 18+.

```bash
git clone https://github.com/quantsingularity/RiskOptimizer.git
cd RiskOptimizer

# Blockchain
cd code/blockchain
npm install

# Backend
cd ../backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Quant library
cd ../quant_ml
pip install -r requirements.txt

# Web frontend
cd ../../web-frontend
npm install

# Mobile frontend
cd ../mobile-frontend
npm install
```

For an automated setup:

```bash
git clone https://github.com/quantsingularity/RiskOptimizer.git
cd RiskOptimizer
./scripts/setup_environment.sh
./scripts/run_riskoptimizer.sh
```

Full, environment-specific instructions are in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Running the Stack

```bash
# 1) Supporting services (from infrastructure/docker, Docker required)
docker compose -f docker-compose.yml up -d postgres redis

# 2) Local chain (from code/blockchain)
npx hardhat node                   # local chain at http://127.0.0.1:8545

# 3) Backend (from code/backend, venv active)
python app.py                      # serves http://0.0.0.0:5000

# 4) Celery worker, optional (from code/backend, venv active)
celery -A src.tasks.celery_app worker --loglevel=info

# 5) Web dashboard (from web-frontend)
npm run dev

# 6) Mobile app (from mobile-frontend)
npm start                          # press w for web, a for Android, i for iOS
```

See [docs/USAGE.md](docs/USAGE.md) and [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## API Surface

Base URL `http://localhost:5000`.

| Group      | Prefix               | Highlights                                                                               |
| :--------- | :------------------- | :--------------------------------------------------------------------------------------- |
| Auth       | `/api/v1/auth`       | `register`, `login`, `refresh`, `logout`                                                 |
| Portfolio  | `/api/v1/portfolios` | `address/{address}`, `address/{address}/onchain`, `save`, `{id}`, `user/{user_id}`       |
| Risk       | `/api/v1/risk`       | `var`, `cvar`, `sharpe-ratio`, `max-drawdown`, `portfolio-metrics`, `efficient-frontier` |
| Blockchain | `/api/v1/blockchain` | `transactions/{portfolio_id}`, `verify/{portfolio_id}`                                   |
| Monitoring | `/api/v1/monitoring` | `performance`, `endpoints`, `system`, `cache`, `database`, `optimize`                    |

Full request and response shapes are in [docs/API.md](docs/API.md).

## Testing

```bash
# Backend (from code/backend)
pytest

# Smart contracts (from code/blockchain)
npx hardhat test

# Quant library (from code/quant_ml)
pytest

# Web (from web-frontend)
npm test

# Mobile (from mobile-frontend)
npm test
```

The backend suite covers unit and integration tests for the domain services and API controllers. The Hardhat suite covers each contract individually. `quant_ml` has its own pytest suite covering model performance and a general test suite, and the mobile app has 8 real test files, but neither currently runs in CI. The web dashboard has Vitest configured but no test files yet.

## CI/CD Pipeline

GitHub Actions (`.github/workflows/cicd.yml`) runs four jobs on push, pull request, and manual dispatch:

| Job                  | Depends on          | What it does                                                                       |
| :------------------- | :------------------ | :--------------------------------------------------------------------------------- |
| Code Quality Checks  | -                   | Python formatter checks (autoflake, black) and a repository-wide Prettier check    |
| Backend Tests        | Code Quality Checks | Runs the pytest suite with coverage and uploads the coverage report as an artifact |
| Smart Contract Tests | Code Quality Checks | Compiles the contracts with Hardhat and runs the contract test suite               |
| Frontend Build       | Code Quality Checks | Installs dependencies and produces the production web build (no test step)         |

There is currently no CI job for `quant_ml` or the mobile app.

## Documentation

| Document                                                     | Contents                               |
| :----------------------------------------------------------- | :------------------------------------- |
| [docs/README.md](docs/README.md)                             | Documentation index                    |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                 | System architecture                    |
| [docs/API.md](docs/API.md)                                   | REST API reference                     |
| [docs/INSTALLATION.md](docs/INSTALLATION.md)                 | Setup for all components               |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md)               | Environment variables and config       |
| [docs/USAGE.md](docs/USAGE.md)                               | Running and using the platform         |
| [docs/CLI.md](docs/CLI.md)                                   | Helper scripts reference               |
| [docs/FEATURE_MATRIX.md](docs/FEATURE_MATRIX.md)             | Feature status, implemented vs planned |
| [docs/ML_MODEL_PERFORMANCE.md](docs/ML_MODEL_PERFORMANCE.md) | Model evaluation methodology           |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)           | Common issues and fixes                |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)                 | Contribution guide                     |
| [docs/examples/](docs/examples/)                             | Worked examples                        |

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
