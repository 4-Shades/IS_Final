# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Base Stage: Shared Environment Settings
# ------------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


# ------------------------------------------------------------------------------
# Builder: API Dependencies
# ------------------------------------------------------------------------------
FROM base AS api-builder

WORKDIR /build

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV"

COPY requirements.api.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt


# ------------------------------------------------------------------------------
# Builder: UI Dependencies
# ------------------------------------------------------------------------------
FROM base AS ui-builder

WORKDIR /build

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV"

COPY requirements.ui.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt


# ------------------------------------------------------------------------------
# Base Runtime: Non-root User Setup
# ------------------------------------------------------------------------------
FROM base AS runtime-base

WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app


# ------------------------------------------------------------------------------
# Runtime: API Service
# ------------------------------------------------------------------------------
FROM runtime-base AS api-runtime

ENV APP_MODULE=agents.host_agent.__main__ \
    PORT=8000

COPY --from=api-builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"
COPY --chown=app:app agents ./agents
COPY --chown=app:app common ./common
COPY --chown=app:app shared ./shared

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/healthz')" || exit 1

CMD ["python", "-m", "common.serve"]


# ------------------------------------------------------------------------------
# Runtime: UI Service
# ------------------------------------------------------------------------------
FROM runtime-base AS ui-runtime

COPY --from=ui-builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"
COPY --chown=app:app travel_ui.py ./
COPY --chown=app:app shared ./shared

USER app

EXPOSE 8501

CMD ["streamlit", "run", "travel_ui.py", "--server.address=0.0.0.0", "--server.port=8501"]


# Default target image
FROM api-runtime AS runtime