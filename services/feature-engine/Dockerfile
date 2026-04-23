FROM python:3.11.15-slim-bookworm AS apex-core-builder

ARG RUST_TOOLCHAIN=stable

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"
ENV RUSTFLAGS="-C target-feature=+sse4.2,+fma"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain "${RUST_TOOLCHAIN}"

RUN python -m pip install --upgrade "pip<26" \
    && pip install --no-cache-dir "maturin>=1.7,<2"

WORKDIR /build
COPY shared_rs /build/shared_rs
WORKDIR /build/shared_rs/apex_core
RUN maturin build --release --interpreter /usr/local/bin/python3.11

FROM python:3.11.15-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app:/app/shared/python/src

WORKDIR /app

RUN python -m pip install --upgrade "pip<26" \
    && addgroup --system appuser \
    && adduser --system --uid 10001 --ingroup appuser appuser

COPY --from=apex-core-builder /build/shared_rs/target/wheels /tmp/apex_wheels
RUN pip install --no-cache-dir /tmp/apex_wheels/*.whl \
    && rm -rf /tmp/apex_wheels

COPY constraints-runtime.txt /app/constraints-runtime.txt
COPY config /app/config
COPY shared/python /app/shared/python
COPY shared/contracts /app/shared/contracts
COPY services/feature-engine /app/services/feature-engine

WORKDIR /app/services/feature-engine
RUN pip install --no-cache-dir -c /app/constraints-runtime.txt -e /app/shared/python \
    && pip install --no-cache-dir -c /app/constraints-runtime.txt -e . \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8020
CMD ["python", "-m", "feature_engine.main"]
