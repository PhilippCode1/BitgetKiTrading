FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade "pip<26" \
    && addgroup --system appuser \
    && adduser --system --uid 10001 --ingroup appuser appuser

COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY infra/migrations/postgres /app/infra/migrations/postgres
COPY shared/python /app/shared/python
COPY shared/contracts /app/shared/contracts
COPY services/api-gateway /app/services/api-gateway

WORKDIR /app/services/api-gateway
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
CMD ["python", "-m", "api_gateway.app"]


