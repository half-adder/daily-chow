# Deployment

Daily Chow is deployed as a Docker Compose stack on a DigitalOcean VPS, accessible at `https://chow.seanjohnsen.com`.

## Architecture

```
Internet → Cloudflare (proxy) → VPS:443 → Caddy
                                          ├── /        → SvelteKit (Node, port 3000)
                                          └── /api/*   → FastAPI (Uvicorn, port 8000)
```

Three Docker Compose services on a single VPS:

- **caddy** — Reverse proxy with auto-TLS via Let's Encrypt (Cloudflare DNS challenge). Exposes ports 80/443.
- **frontend** — SvelteKit built with `adapter-node`, served by Node. Internal network only.
- **backend** — FastAPI + Uvicorn serving the solver API. Internal network only.

## CI/CD

Push to `main` triggers automatic deployment via GitHub Actions:

1. **Build** — Three images built in parallel on GitHub runners (~1-2 min)
2. **Push** — Images pushed to ghcr.io
3. **Deploy** — SSH into VPS, `git pull`, `docker compose pull`, `docker compose up -d`
4. **Health check** — `curl /api/health` to verify

Workflow: `.github/workflows/deploy.yml`

### GitHub Secrets

| Secret | Description |
|--------|-------------|
| `VPS_HOST` | VPS public IP |
| `VPS_SSH_KEY` | Deploy key (stored in 1Password: "Daily Chow - Deploy Key") |

### VPS Docker Registry Auth

The VPS is authenticated with ghcr.io via `~/.docker/config.json`. If auth expires, re-authenticate from your local machine using `gh auth token`.

## VPS .env

Located at `/opt/daily-chow/.env` (mode 600, not in repo):

```bash
SITE_ADDRESS=chow.seanjohnsen.com
ORIGIN=https://chow.seanjohnsen.com
CLOUDFLARE_API_TOKEN=<from 1Password: "Cloudflare - DNS API Token">
```

## Manual Deploy

If CI/CD is down or you need to deploy without pushing:

```bash
ssh <user>@<vps> "cd /opt/daily-chow && git pull origin main && docker compose pull && docker compose up -d"
```

## Verify

```bash
curl https://chow.seanjohnsen.com/api/health
# {"status":"ok"}
```

## Docker Networking

Docker's iptables manipulation is disabled (`/etc/docker/daemon.json: {"iptables": false}`) to prevent Docker from bypassing UFW. This means containers can't reach the internet by default. Manual iptables rules provide outbound NAT for the Docker bridge subnet, persisted via `iptables-persistent`.

If containers lose internet after a `docker compose down && up` (new network ID), re-run the masquerade rule with the new bridge interface and `sudo netfilter-persistent save`.

## Files

```
docker-compose.yml                # Service definitions (image + build)
Dockerfile.backend                # Python 3.13 + uv
Dockerfile.frontend               # Multi-stage bun build → node runtime
Dockerfile.caddy                  # Custom Caddy with Cloudflare DNS plugin
Caddyfile                         # Reverse proxy config
.dockerignore                     # Build context exclusions
.env.example                      # Template for VPS .env
.github/workflows/deploy.yml      # CI/CD pipeline
```

## Resource Usage

- Backend: ~150MB RAM (Python + OR-Tools)
- Frontend: ~80MB RAM (Node)
- Caddy: ~20MB RAM
- Total: ~250MB of 1GB available

> **Note:** Private infrastructure details (IPs, zone IDs, SSH config) are in the Obsidian vault under `01. Projects/Daily-Chow/Daily Chow Infrastructure`.
