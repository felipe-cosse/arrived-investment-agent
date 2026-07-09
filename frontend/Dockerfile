# Frontend image (spec §11): node build stage → nginx serving dist/, proxying /api.
# Base images pinned by major tag (R24); package-lock.json pins dependencies.

# --- Stage 1: type-check and build the static bundle ---------------------------
FROM node:22-alpine AS build

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tailwind.config.ts postcss.config.js ./
COPY src ./src
# `npm run build` = `tsc --noEmit && vite build` (package.json); CI runs vitest.
RUN npm run build

# --- Stage 2: nginx runtime -----------------------------------------------------
FROM nginx:1-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist /usr/share/nginx/html

EXPOSE 80
