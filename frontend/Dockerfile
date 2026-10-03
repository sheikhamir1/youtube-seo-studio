# ---------------------------------------------------------------------------
# YouTube SEO Studio - frontend image
# Stage 1 builds the Vite bundle, stage 2 serves it with Nginx.
# ---------------------------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (cached across source changes).
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA fallback + /api proxy (including unbuffered SSE) is configured here.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
