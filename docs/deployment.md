# Deployment

Daily Chow is deployed as a Docker Compose stack on a DigitalOcean VPS (`homer`), accessible at `https://chow.seanjohnsen.com`.

## Architecture

```
Internet → Cloudflare (proxy) → VPS:443 → Caddy
                                          ├── /        → SvelteKit (Node, port 3000)
                                          └── /api/*   → FastAPI (Uvicorn, port 8000)
```

Three Docker Compose services on a single VPS (co-located with Obsidian sync infrastructure):

- **caddy** — Reverse proxy with auto-TLS via Let's Encrypt (Cloudflare DNS challenge). Exposes ports 80/443.
- **frontend** — SvelteKit built with `adapter-node`, served by Node. Internal network only.
- **backend** — FastAPI + Uvicorn serving the solver API. Internal network only.

## Infrastructure

| Component | Details |
|-----------|---------|
| **VPS** | DigitalOcean `homer`, 1GB RAM / 1 vCPU, NYC3 (`<VPS_IP>`) |
| **DNS** | Cloudflare proxied A record: `chow` → `<VPS_IP>` |
| **SSL** | Cloudflare Full (Strict) + Caddy Let's Encrypt cert via DNS challenge |
| **Firewall** | UFW: allow 22, 80, 443, 22000 (Syncthing) |
| **Docker** | `iptables: false` in daemon.json (UFW bypass prevention), manual NAT masquerade for container outbound |
| **SSH** | `<VPS_USER>@<VPS_IP>` (key-only, fail2ban active) or via Tailscale at `<TAILSCALE_IP>` |

## VPS .env

Located at `/opt/daily-chow/.env` (mode 600, not in repo):

```bash
SITE_ADDRESS=chow.seanjohnsen.com
ORIGIN=https://chow.seanjohnsen.com
CLOUDFLARE_API_TOKEN=<from 1Password: "Cloudflare - DNS API Token">
```

## Deploy

```bash
# From local machine — rsync code and rebuild
rsync -avz --exclude='.git' --exclude='node_modules' --exclude='.svelte-kit' \
  --exclude='__pycache__' --exclude='.venv' --exclude='.worktrees' \
  --exclude='docs' --exclude='.DS_Store' --exclude='*.png' \
  -e "ssh -i ~/.ssh/id_ed25519" \
  /Users/sean/code/daily-chow/.worktrees/web-deployment/ \
  <VPS_USER>@<VPS_IP>:/opt/daily-chow/

# On VPS — rebuild and restart
ssh -i ~/.ssh/id_ed25519 <VPS_USER>@<VPS_IP> \
  "cd /opt/daily-chow && docker compose up -d --build"
```

## Verify

```bash
curl https://chow.seanjohnsen.com/api/health
# {"status":"ok"}
```

## Docker Networking

Docker's iptables manipulation is disabled (`/etc/docker/daemon.json: {"iptables": false}`) to prevent Docker from bypassing UFW. This means containers can't reach the internet by default. Manual iptables rules provide outbound NAT:

```bash
# These are persisted via iptables-persistent
iptables -t nat -A POSTROUTING -s 172.18.0.0/16 ! -o br-<network-id> -j MASQUERADE
iptables -A FORWARD -s 172.18.0.0/16 -j ACCEPT
iptables -A FORWARD -d 172.18.0.0/16 -j ACCEPT
```

If containers lose internet after a `docker compose down && up` (new network ID), re-run the masquerade rule with the new bridge interface and `sudo netfilter-persistent save`.

## Files

```
docker-compose.yml      # Service definitions
Dockerfile.backend      # Python 3.13 + uv
Dockerfile.frontend     # Multi-stage bun build → node runtime
Dockerfile.caddy        # Custom Caddy with Cloudflare DNS plugin
Caddyfile               # Reverse proxy config
.dockerignore           # Build context exclusions
.env.example            # Template for VPS .env
```

## Resource Usage

- Backend: ~150MB RAM (Python + OR-Tools)
- Frontend: ~80MB RAM (Node)
- Caddy: ~20MB RAM
- Total: ~250MB of 1GB available
