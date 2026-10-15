# ==========================================
# Stage 1: Build React Application
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies using cached layer
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code and config
COPY . .

# Build argument for API base URL with sensible fallback
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# Build static production bundle
RUN npm run build

# ==========================================
# Stage 2: Serve with Nginx Alpine
# ==========================================
FROM nginx:alpine

# Remove default nginx configuration
RUN rm -rf /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration with SPA fallback
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built production assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
