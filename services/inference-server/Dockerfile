# Optional GPU: Overlay docker-compose.inference-gpu.yml (gpus: all).
# Basis-Image CPU — TimesFM-Echtlast kann spaeter auf CUDA-Runtime-Image umgestellt werden.
FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src:/app/services/inference-server/src

WORKDIR /app

RUN python -m pip install --upgrade "pip<26" \
    && addgroup --system appuser \
    && adduser --system --uid 10001 --ingroup appuser appuser

COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY shared/python /app/shared/python
COPY shared/contracts /app/shared/contracts
COPY services/inference-server /app/services/inference-server

WORKDIR /app/services/inference-server
# Torch CPU-Wheel (GPU: Overlay-Image mit cu124 + passendem torch-index)
RUN pip install --no-cache-dir "torch>=2.2.0" --index-url "https://download.pytorch.org/whl/cpu" \
    && pip install --no-cache-dir "sentence-transformers>=3.0.0"
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 50051
EXPOSE 8140

CMD ["python", "-m", "inference_server.main"]
