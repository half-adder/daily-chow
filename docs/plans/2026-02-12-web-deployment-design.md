# Daily Chow Web Deployment Design

## Goal

Deploy Daily Chow as a self-hosted web app on an existing DigitalOcean VPS, accessible at `chow.<domain>.com`.

## Architecture

```
Internet → Cloudflare (proxy) → VPS:443 → Caddy
                                            ├── /        → SvelteKit (Node, port 3000)
                                            └── /api/*   → FastAPI (Uvicorn, port 8000)
```

Three Docker Compose services on a single VPS (co-located with existing Obsidian sync):

- **caddy** — Reverse proxy. Routes `/api/*` to backend, everything else to frontend. Auto-provisions TLS via Let's Encrypt using Cloudflare DNS challenge. Exposes ports 80/443.
- **frontend** — SvelteKit built with `adapter-node`, served by Node. Internal network only.
- **backend** — FastAPI + Uvicorn serving the solver API. Internal network only.

## Key Decisions

- **Stateless** — No database. Persistence can be added later.
- **Public, no auth** — Anyone with the URL can use it.
- **Caddy over Nginx** — Auto-HTTPS, minimal config (~10 lines), built-in Cloudflare DNS plugin.
- **adapter-node** — Replaces `adapter-auto` for proper Docker/Node deployment.
- **Build on VPS** — No container registry. CI/CD SSHes in and builds locally.

## Docker Compose

```yaml
services:
  caddy:
    build:
      context: .
      dockerfile: Dockerfile.caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - caddy_data:/data
      - caddy_config:/config
    env_file: .env
    depends_on:
      - frontend
      - backend

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    expose:
      - "3000"

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    expose:
      - "8000"

volumes:
  caddy_data:
  caddy_config:
```

## Dockerfiles

### Backend (`Dockerfile.backend`)

- Base: `python:3.12-slim`
- Install `uv`, copy `pyproject.toml` + `uv.lock`, install deps
- Copy `src/daily_chow/`
- CMD: `uvicorn daily_chow.api:app --host 0.0.0.0 --port 8000`

### Frontend (`Dockerfile.frontend`)

- Multi-stage build
- Stage 1 (build): `oven/bun` image, copy `frontend/`, run `bun install && bun run build`
- Stage 2 (runtime): `node:22-slim`, copy build output
- CMD: `node build/index.js`

### Caddy (`Dockerfile.caddy`)

- Custom Caddy image with Cloudflare DNS plugin (built via `caddy:builder`)
- Copy `Caddyfile` into image

## Caddyfile

```
chow.{$DOMAIN} {
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy backend:8000
    }
    handle {
        reverse_proxy frontend:3000
    }
    tls {
        dns cloudflare {$CLOUDFLARE_API_TOKEN}
    }
}
```

## DNS & TLS

1. Namecheap nameservers pointed to Cloudflare
2. Cloudflare A record: `chow` → VPS IP (proxied, orange cloud)
3. Cloudflare SSL mode: **Full (Strict)**
4. Caddy provisions Let's Encrypt cert via Cloudflare DNS challenge

## CI/CD (GitHub Actions)

**Trigger:** Push to `main`.

**Workflow:**
1. GitHub Actions runner SSHes into VPS
2. Runs `git pull && docker compose up -d --build`
3. Health check: `curl -f https://chow.<domain>.com/api/health` (add a `/health` endpoint to FastAPI)

**GitHub Secrets:**
- `VPS_HOST` — droplet IP or hostname
- `VPS_SSH_KEY` — SSH private key for deploy user

**VPS `.env` file (not in repo):**
- `CLOUDFLARE_API_TOKEN` — for Caddy DNS challenge
- `DOMAIN` — the base domain

## Frontend Changes Needed

- Switch `adapter-auto` to `adapter-node` in `svelte.config.js`
- Add `ORIGIN` env var support for adapter-node (CSRF protection)
- Update API base URL to use relative `/api` paths (should already work given current vite proxy setup)

## Resource Estimate

- Backend: ~150MB RAM (Python + OR-Tools)
- Frontend: ~80MB RAM (Node)
- Caddy: ~20MB RAM
- Total: ~250MB

## Files to Create

```
docker-compose.yml
Dockerfile.backend
Dockerfile.frontend
Dockerfile.caddy
Caddyfile
.github/workflows/deploy.yml
.dockerignore
```
