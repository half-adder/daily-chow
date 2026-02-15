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
| **Registry** | `ghcr.io/half-adder/daily-chow-{backend,frontend,caddy}` |

## CI/CD

Push to `main` triggers automatic deployment via GitHub Actions:

1. **Build** — Three images built in parallel on GitHub runners (~1-2 min)
2. **Push** — Images pushed to `ghcr.io/half-adder/daily-chow-*`
3. **Deploy** — SSH into VPS, `git pull`, `docker compose pull`, `docker compose up -d`
4. **Health check** — `curl /api/health` to verify

Workflow: `.github/workflows/deploy.yml`

### GitHub Secrets

| Secret | Value |
|--------|-------|
| `VPS_HOST` | `<VPS_IP>` |
| `VPS_SSH_KEY` | Private key for `<VPS_USER>` (stored in 1Password: "Daily Chow - Deploy Key") |

### VPS Docker Registry Auth

The VPS is authenticated with `ghcr.io` via `~/.docker/config.json`. If auth expires, re-authenticate:

```bash
# From local machine (uses gh CLI token)
ssh -i ~/.ssh/id_ed25519 <VPS_USER>@<VPS_IP> \
  "docker login ghcr.io -u half-adder --password-stdin" <<< "$(gh auth token)"
```

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
ssh -i ~/.ssh/id_ed25519 <VPS_USER>@<VPS_IP> \
  "cd /opt/daily-chow && git pull origin main && docker compose pull && docker compose up -d"
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

## Cloudflare DNS

Managed via API using the DNS token from 1Password:

```bash
# Example: list records
CF_TOKEN=$(op item get "Cloudflare - DNS API Token " --fields label=credential --reveal)
curl -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/<CLOUDFLARE_ZONE_ID>/dns_records"
```

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
