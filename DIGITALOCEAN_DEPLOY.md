# Content Pipeline — DigitalOcean Deployment Guide

This deploys the `content-pipeline` FastAPI service alongside your existing n8n
instance. The service exposes the deterministic Python math guardrails and the
POS-confirmed lexical injector over HTTPS so n8n can call them via HTTP nodes.

---

## 1. Which Droplet to Use

**Option A — Same Droplet as n8n (recommended to start)**
If your n8n instance runs on a DigitalOcean Droplet with ≥ 2 vCPU / 4GB RAM,
add the service to the same machine. It uses ~200MB RAM idle, ~400MB under load.
The service communicates with n8n over `localhost:8080` — no public exposure needed.

**Option B — Dedicated Droplet**
If n8n is on a cloud instance (voyagerscontent.app.n8n.cloud is hosted, not your
server), spin up a separate $12/month Basic Droplet (2 vCPU / 2GB RAM, Ubuntu 24.04).
The service will be exposed over HTTPS and n8n calls it by domain.

---

## 2. Initial Server Setup

```bash
# SSH into your Droplet
ssh root@YOUR_DROPLET_IP

# Update packages
apt-get update && apt-get upgrade -y

# Install Docker (one command)
curl -fsSL https://get.docker.com | sh

# Install nginx + certbot for HTTPS
apt-get install -y nginx certbot python3-certbot-nginx

# Create a non-root deploy user
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
```

---

## 3. Deploy the Service

```bash
# Switch to deploy user
su - deploy

# Clone the repo (or pull the latest)
git clone https://github.com/voyagerscontent/galapagosislands-travel-content-system.git
cd galapagosislands-travel-content-system

# Create .env with your secrets (never committed)
cat > .env << 'ENVEOF'
PIPELINE_SERVICE_KEY=<generate with: openssl rand -hex 32>
GOOGLE_DRIVE_CREDENTIAL_ID=BXOLO4YcNnpHp3SD
AIRTABLE_PAT=<your airtable PAT>
N8N_API_KEY=<your n8n API key>
ENVEOF

# Build and start
docker compose up -d --build

# Verify it started
curl http://localhost:8080/health
# Expected: {"ok":true,"version":"1.1.0"}
```

---

## 4. HTTPS with Nginx (Option B — public URL)

```bash
# Point a subdomain at your Droplet IP in your DNS (A record):
#   pipeline.galapagosislands.travel → YOUR_DROPLET_IP

# Copy the nginx config
sudo cp engine/n8n-production/nginx_content_pipeline.conf \
     /etc/nginx/sites-available/content-pipeline

# Edit the server_name line
sudo nano /etc/nginx/sites-available/content-pipeline
# Change: server_name pipeline.yourdomain.com;
# To:     server_name pipeline.galapagosislands.travel;

# Enable site
sudo ln -s /etc/nginx/sites-available/content-pipeline \
           /etc/nginx/sites-enabled/content-pipeline
sudo nginx -t && sudo systemctl reload nginx

# Get Let's Encrypt certificate (free, auto-renews)
sudo certbot --nginx -d pipeline.galapagosislands.travel

# Test HTTPS
curl https://pipeline.galapagosislands.travel/health
```

---

## 5. Wire n8n to the Service

Run the wiring script from your local machine (or the Droplet):

```bash
export PIPELINE_SERVICE_URL=https://pipeline.galapagosislands.travel
export PIPELINE_SERVICE_KEY=<the key you put in .env>
export N8N_PUB=<your n8n API key>

python engine/n8n-production/wire_pipeline_service.py
```

This:
1. Patches `WFP5_humanize.json` — adds `/verify` + `/lexical/inject` HTTP nodes
   after the De-AI Dictionary, replacing the inline JS version.
2. Patches `WFP7_auditor.json` — replaces the 258KB inline BCP JS blob with a
   clean HTTP call to `/lexical/inject` (full POS, per-paragraph salt).
3. Pushes both patched workflows to your live n8n instance via the n8n API.
4. Saves the patched JSONs back to the repo files.

Then commit:
```bash
git add engine/n8n-production/WFP5_humanize.json engine/n8n-production/WFP7_auditor.json
git commit -m "Wire content-pipeline service into WFP5 + WFP7 (POS injection, per-para salt)"
```

---

## 6. Same-Droplet Setup (Option A — n8n on your own server)

If n8n runs on the same machine, set `PIPELINE_SERVICE_URL=http://localhost:8080`
in the wiring script — no nginx or HTTPS needed. The Docker container binds to
`127.0.0.1:8080` so it's inaccessible from the internet.

```bash
export PIPELINE_SERVICE_URL=http://localhost:8080
export PIPELINE_SERVICE_KEY=""   # empty — no auth needed for loopback
export N8N_PUB=<your n8n API key>
python engine/n8n-production/wire_pipeline_service.py
```

---

## 7. Keep the Service Updated

```bash
# Pull new code + rebuild (zero-downtime: docker compose handles restart)
git pull
docker compose up -d --build

# If the lexicon.json changes (new workbook), rebuild is all that's needed —
# the Dockerfile bakes the lexicon in at build time.
```

---

## 8. Monitor

```bash
# Live logs
docker compose logs -f content-pipeline

# Health check
curl https://pipeline.galapagosislands.travel/health

# Test injection manually
curl -X POST https://pipeline.galapagosislands.travel/lexical/inject \
  -H "Content-Type: application/json" \
  -H "X-Pipeline-Key: YOUR_KEY" \
  -d '{"text": "The snorkel was amazing. The water was pristine. Sea lions swam close.\n\nThe panga ride felt peaceful. The birds were incredible. You enjoy the quiet highlands."}'
```

Expected response includes `replacements` (amazing → iridescent, etc.),
`salted_paragraphs: 2` (one per paragraph), `salt_long` and `salt_phrase` counts.

---

## Cost

| Option | Droplet size | Monthly cost |
|--------|-------------|--------------|
| A (same as n8n) | Add to existing | $0 extra |
| B (dedicated, public URL) | 2 vCPU / 2GB Basic | ~$12/month |

The service handles ~50 concurrent inject calls on a 2-vCPU droplet.
For the current production volume (< 100 pages/day), Option A or the $12 droplet
is more than enough.
