FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src

WORKDIR /app

RUN python -m pip install --upgrade "pip<26" \
    && addgroup --system appuser \
    && adduser --system --uid 10001 --ingroup appuser appuser

COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY shared/python /app/shared/python
COPY services/audit-ledger /app/services/audit-ledger

WORKDIR /app/services/audit-ledger
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8098
CMD ["python", "-m", "audit_ledger.main"]
