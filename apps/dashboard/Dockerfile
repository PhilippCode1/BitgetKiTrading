FROM node:20.19.6-alpine3.22 AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="${PNPM_HOME}:${PATH}"
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@10.30.1 --activate

FROM base AS deps

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json prettier.config.cjs /app/
COPY apps/dashboard/package.json /app/apps/dashboard/package.json
COPY shared/ts/package.json /app/shared/ts/package.json

RUN pnpm install --frozen-lockfile

FROM base AS builder

ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_WS_BASE_URL
ARG NEXT_PUBLIC_APP_NAME=bitget-btc-ai
ARG NEXT_PUBLIC_ENABLE_ADMIN=false
ARG NEXT_PUBLIC_ENABLE_NEWS=true
ARG NEXT_PUBLIC_ENABLE_TELEGRAM_STATUS=true

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_WS_BASE_URL=${NEXT_PUBLIC_WS_BASE_URL}
ENV NEXT_PUBLIC_APP_NAME=${NEXT_PUBLIC_APP_NAME}
ENV NEXT_PUBLIC_ENABLE_ADMIN=${NEXT_PUBLIC_ENABLE_ADMIN}
ENV NEXT_PUBLIC_ENABLE_NEWS=${NEXT_PUBLIC_ENABLE_NEWS}
ENV NEXT_PUBLIC_ENABLE_TELEGRAM_STATUS=${NEXT_PUBLIC_ENABLE_TELEGRAM_STATUS}

COPY --from=deps /app/ /app/
COPY apps/dashboard /app/apps/dashboard
COPY shared/ts /app/shared/ts

RUN if [ -z "${NEXT_PUBLIC_API_BASE_URL}" ] || [ -z "${NEXT_PUBLIC_WS_BASE_URL}" ]; then \
      echo "Dockerfile: NEXT_PUBLIC_API_BASE_URL und NEXT_PUBLIC_WS_BASE_URL sind Pflicht (Browser-URLs zum Gateway)"; \
      exit 1; \
    fi

# Standalone-Output: kein pnpm-Workspace im Laufzeit-Image, nur getracede node_modules
RUN pnpm --dir apps/dashboard build

FROM node:20.19.6-alpine3.22 AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

WORKDIR /app

RUN addgroup -S -g 10001 modul_mate && adduser -S -u 10001 -G modul_mate -H -h /app modul_mate

# next.config distDir: build -> build/standalone + build/static
COPY --from=builder --chown=modul_mate:modul_mate /app/apps/dashboard/build/standalone/ /app/
COPY --from=builder --chown=modul_mate:modul_mate /app/apps/dashboard/build/static /app/apps/dashboard/build/static
COPY --from=builder --chown=modul_mate:modul_mate /app/apps/dashboard/public /app/apps/dashboard/public

# Keine Sourcemaps im Image
RUN find /app -type f -name "*.map" -delete 2>/dev/null || true

# Kein pnpm-Workspace-Root: nur Standalone-Trace (getraces node_modules, kein globales pnpm-Install-Layout)
RUN test -f /app/apps/dashboard/server.js \
  && ! test -f /app/pnpm-workspace.yaml \
  && ! test -f /app/pnpm-lock.yaml

USER modul_mate

EXPOSE 3000

# Node 20: fetch
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "apps/dashboard/server.js"]


