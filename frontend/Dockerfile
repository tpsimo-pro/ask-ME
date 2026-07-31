# --- build stage: compile the Vite app to static assets ---
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

# --- runtime stage: serve the static dist/ output ---
FROM node:20-slim

WORKDIR /app

# `serve` is a minimal static file server; installed globally so no
# package.json changes are needed for a production-only dependency.
RUN npm install -g serve

COPY --from=build /app/dist ./dist

# Railway (and most PaaS) inject $PORT and expect the container to bind to
# it; default to 4173 for local `docker run` without that var set.
ENV PORT=4173
EXPOSE 4173

# -s enables SPA fallback (all unmatched routes serve index.html), which
# react-router-dom's client-side routing requires.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-4173}"]
