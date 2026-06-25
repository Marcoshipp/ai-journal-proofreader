# ── Backend Dockerfile ────────────────────────────────────────────────────────
# Python 3.13-slim + uv. Playwright is installed with system deps for Chromium.
# Context: ./backend

FROM python:3.13-slim AS base

# System deps: curl for uv install + playwright browser dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency manifests first (layer-cache friendly)
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Install Playwright + its Chromium browser and required OS packages
RUN uv run playwright install --with-deps chromium

# Copy source code
COPY . .

# Ensure uploads directory exists
RUN mkdir -p /app/uploads

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
