# syntax=docker/dockerfile:1
# Multi-Stage: Builder mit build-essential + pip; Runtime nur slim+Fonts+installierte Site-Packages (ohne venv-Overhead).
FROM python:3.11.15-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade "pip<26"

COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY infra/migrations/postgres /app/infra/migrations/postgres
COPY shared/python /app/shared/python
COPY shared/contracts /app/shared/contracts
COPY services/api-gateway /app/services/api-gateway

WORKDIR /app/services/api-gateway
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e .

FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system --gid 10001 modul_mate \
    && adduser --system --uid 10001 --ingroup modul_mate --home /app modul_mate

# Nur installierte Distributions-Dateien und Entrypoints — kein Compiler, kein venv-Stub
COPY --from=builder /usr/local/lib/python3.11/ /usr/local/lib/python3.11/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /app /app

WORKDIR /app/services/api-gateway
RUN chown -R modul_mate:modul_mate /app

USER modul_mate

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=50s --retries=3 \
  CMD /usr/local/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

CMD ["/usr/local/bin/python", "-m", "api_gateway.app"]
