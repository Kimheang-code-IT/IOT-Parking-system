# syntax=docker/dockerfile:1
# Smart IoT Parking — Nuxt 4 frontend (production image)
#
# Build context: ../frontend  (docker build -f infrastructure/docker/frontend.Dockerfile frontend)
# Multi-stage: pnpm install -> nuxt build -> run the Nitro server (never `nuxt dev`).

# ---------------------------------------------------------------- deps
FROM node:22-alpine AS deps
ENV NUXT_TELEMETRY_DISABLED=1
RUN npm install -g pnpm@10.30.3
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# --ignore-scripts: the postinstall `nuxt prepare` needs the source tree;
# it runs implicitly during `pnpm build` in the next stage instead.
RUN pnpm install --frozen-lockfile --ignore-scripts

# ---------------------------------------------------------------- build
FROM node:22-alpine AS build
ENV NUXT_TELEMETRY_DISABLED=1
RUN npm install -g pnpm@10.30.3
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

# ---------------------------------------------------------------- runtime
FROM node:22-alpine AS runtime
ENV NODE_ENV=production \
    NUXT_TELEMETRY_DISABLED=1 \
    NITRO_PORT=3000 \
    NITRO_HOST=0.0.0.0

WORKDIR /app
# Nitro output is self-contained (bundled server + node_modules)
COPY --from=build --chown=node:node /app/.output ./.output

USER node
EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
