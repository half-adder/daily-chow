# VPS Setup Guide

Steps to deploy Daily Chow on your existing DigitalOcean VPS.

## 1. Cloudflare DNS

1. Log into Cloudflare, select your domain
2. Go to **DNS > Records**, add:
   - Type: `A`
   - Name: `chow`
   - IPv4: your VPS IP
   - Proxy status: **Proxied** (orange cloud)
3. Go to **SSL/TLS > Overview**, set mode to **Full (Strict)**

If your Namecheap nameservers aren't already pointed to Cloudflare, update them:
- In Namecheap, go to **Domain > Nameservers > Custom DNS**
- Enter the two Cloudflare nameservers shown in your Cloudflare dashboard

## 2. Cloudflare API Token

Caddy needs a token to provision TLS certs via DNS challenge.

1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Click **Create Token**
3. Use the **Edit zone DNS** template
4. Scope it to your specific zone (domain)
5. Copy the token — you'll need it for the `.env` file on the VPS

## 3. VPS: Create Deploy User

SSH into your VPS as root:

```bash
# Create deploy user
adduser --disabled-password deploy

# Give deploy user docker access
usermod -aG docker deploy

# Set up SSH key auth
mkdir -p /home/deploy/.ssh
# Paste your deploy public key:
nano /home/deploy/.ssh/authorized_keys
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
```

## 4. VPS: Install Docker

If Docker isn't already installed:

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh

# Verify
docker --version
docker compose version
```

## 5. VPS: Clone and Configure

As the `deploy` user:

```bash
# Clone the repo
sudo mkdir -p /opt/daily-chow
sudo chown deploy:deploy /opt/daily-chow
git clone https://github.com/YOUR_USER/daily-chow.git /opt/daily-chow
cd /opt/daily-chow

# Create .env from the example
cp .env.example .env
nano .env
```

Fill in `.env`:

```bash
SITE_ADDRESS=chow.yourdomain.com
ORIGIN=https://chow.yourdomain.com
CLOUDFLARE_API_TOKEN=your_token_from_step_2
```

## 6. VPS: First Deploy

```bash
cd /opt/daily-chow
docker compose up -d --build
```

This will take a few minutes on the first run (building images, downloading dependencies). Once done:

```bash
# Check all 3 services are running
docker compose ps

# Test health endpoint
curl http://localhost/api/health
# Expected: {"status":"ok"}

# Check Caddy logs for TLS cert provisioning
docker compose logs caddy
```

Visit `https://chow.yourdomain.com` in your browser — it should be live.

## 7. GitHub: Add Deploy Secrets

For CI/CD to work on push to `main`:

1. Go to your repo on GitHub > **Settings > Secrets and variables > Actions**
2. Add two repository secrets:
   - `VPS_HOST` — your VPS IP address (or `chow.yourdomain.com`)
   - `VPS_SSH_KEY` — the **private** key corresponding to the public key you added in step 3

## 8. Generate a Deploy Key Pair

If you don't already have a dedicated deploy key:

```bash
# On your local machine
ssh-keygen -t ed25519 -f ~/.ssh/daily-chow-deploy -C "daily-chow-deploy"

# The public key goes on the VPS (step 3):
cat ~/.ssh/daily-chow-deploy.pub

# The private key goes in GitHub secrets (step 7):
cat ~/.ssh/daily-chow-deploy
```

## 9. Test CI/CD

Push a commit to `main` and check:
- GitHub Actions > your repo > Actions tab — the deploy workflow should run
- It SSHes into the VPS, pulls, rebuilds, and health-checks

## Troubleshooting

**Caddy won't start / TLS errors:**
- Check the Cloudflare API token has Zone DNS Edit permission
- Check `docker compose logs caddy` for specific errors
- Ensure Cloudflare SSL mode is Full (Strict), not Flexible

**Frontend returns 502:**
- The frontend container may still be starting: `docker compose logs frontend`
- Check that `ORIGIN` in `.env` matches your actual URL (including `https://`)

**API returns 502:**
- Check backend logs: `docker compose logs backend`
- OR-Tools is large — the first build may need time

**Rebuild after changes:**
```bash
docker compose up -d --build
```

**View logs:**
```bash
docker compose logs -f          # all services
docker compose logs -f backend  # just backend
```

**Restart everything:**
```bash
docker compose down && docker compose up -d
```
