# ── Stage 1: Build ───────────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app

# Copy dependency manifests first — own layer so source changes don't bust cache
COPY package.json package-lock.json ./

RUN npm install

# Copy env file so Vite bakes VITE_API_URL into the bundle at build time
COPY .env.production .env.production

# Copy source and build
COPY . .
RUN npm run build

# ── Stage 2: Runtime ─────────────────────────────────────────────────────────
FROM nginx:alpine

# Remove default Nginx placeholder page
RUN rm -rf /usr/share/nginx/html/*

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy our Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]