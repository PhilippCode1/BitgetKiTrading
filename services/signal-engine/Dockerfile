# syntax=docker/dockerfile:1
FROM python:3.11.15-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade "pip<26"

ENV PATH="/opt/venv/bin:$PATH"
COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY shared/python /app/shared/python
COPY shared/contracts /app/shared/contracts
COPY services/signal-engine /app/services/signal-engine
WORKDIR /app/services/signal-engine
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e .
FROM python:3.11.15-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN addgroup --system --gid 10001 modul_mate \
    && adduser --system --uid 10001 --ingroup modul_mate --home /app modul_mate
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app
WORKDIR /app/services/signal-engine
RUN chown -R modul_mate:modul_mate /app
USER modul_mate
EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD /opt/venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/health', timeout=4)" || exit 1
CMD ["/opt/venv/bin/python", "-m", "signal_engine.main"]
