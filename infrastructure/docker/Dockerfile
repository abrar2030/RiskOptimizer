# Backend image for the RiskOptimizer Flask API.
# Build context is the repository root so the image can access code/backend.
# Example (from repo root):
#   docker build -f infrastructure/docker/Dockerfile -t riskoptimizer-backend .

# ---- Builder: install Python dependencies into a venv ----
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY code/backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---- Runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8080

# Non-root user
RUN groupadd --system app && useradd --system --gid app --create-home app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY code/backend/ /app/
# blockchain_service.py's proxy (src/services/blockchain_service.py) and
# ai_optimization.py resolve quant_ml/blockchain as siblings of code/backend
# (walking up sys.path at runtime). Mirror that layout inside the image:
# /app plays the role of code/backend, so its siblings land at container
# root, exactly matching code/{backend,blockchain,quant_ml} on disk.
COPY code/blockchain/ /blockchain/
COPY code/quant_ml/ /quant_ml/

RUN chown -R app:app /app /blockchain /quant_ml
USER app

EXPOSE 8080

# Health endpoint served by the Flask app on the single application port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status < 500 else 1)" || exit 1

# app:app is the Flask WSGI callable defined in code/backend/app.py
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "120", "app:app"]
