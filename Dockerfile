# syntax=docker/dockerfile:1
#
# Targets:
#   api-runtime (default)  FastAPI host and specialist agents; APP_MODULE selects the agent.
#                          Used by Compose, AWS ECS, and Railway.
#   ui-runtime             Streamlit frontend.
#
# No pip cache mounts: Railway's builder rejects cache mounts without its own id prefix.

FROM python:3.11-slim AS base

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1


FROM base AS api-builder
RUN python -m venv "$VIRTUAL_ENV"
COPY requirements/api.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


FROM base AS ui-builder
RUN python -m venv "$VIRTUAL_ENV"
COPY requirements/ui.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt


FROM base AS runtime-base
WORKDIR /app
RUN groupadd --system app \
    && useradd --system --gid app --home-dir /app --create-home app


FROM runtime-base AS ui-runtime
COPY --from=ui-builder "$VIRTUAL_ENV" "$VIRTUAL_ENV"
COPY --chown=app:app travel_ui.py ./
COPY --chown=app:app shared ./shared
USER app
EXPOSE 8501
CMD ["streamlit", "run", "travel_ui.py", "--server.address=0.0.0.0", "--server.port=8501"]


# Last stage, so it is what `docker build` produces without --target.
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
