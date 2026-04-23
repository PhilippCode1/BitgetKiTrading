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

RUN pnpm --dir apps/dashboard build

FROM node:20.19.6-alpine3.22 AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

WORKDIR /app

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/build/standalone/ /app/
COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/build/static /app/apps/dashboard/build/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/dashboard/public /app/apps/dashboard/public

USER nextjs

EXPOSE 3000

CMD ["node", "apps/dashboard/server.js"]


