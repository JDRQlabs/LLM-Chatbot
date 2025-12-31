# Hetzner Ephemeral Server Workspace

Minimal tooling to spin up, SSH into, and tear down short-lived Hetzner Cloud servers for prototyping.

Designed for:
- Fast iteration
- No long-running servers
- No secrets committed to Git

---

## Prerequisites (one-time)

### 1. Install and authenticate `hcloud`

Ensure the Hetzner Cloud CLI is installed and authenticated:

```bash
hcloud context list
```

You should already have:

- A Hetzner Cloud API token configured (via hcloud context or HCLOUD_TOKEN)
- The hcloud CLI available in your PATH

Verify access:

```bash
hcloud server list
```

### 2. Create a dedicated SSH key (recommended)

Create a project-scoped SSH key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/hetzner-proto -C "hetzner-proto"
```

Register it with Hetzner:

```bash
hcloud ssh-key create \
  --name hetzner-proto \
  --public-key-from-file ~/.ssh/hetzner-proto.pub
```

### 3. Create a local .env file

```bash
cp .env.example .env
```

Edit `.env` to match your local paths and preferences.
This file is intentionally not committed.

## Quickstart

```bash
make up      # create server
make ssh     # connect via SSH
make down    # delete server (stops billing)
```

## Notes

- SSH uses the ubuntu user with passwordless sudo
- Root login and password authentication are disabled
- Cloud-init is generated locally and never committed
- Servers must be deleted (not stopped) to stop billing

## Cleanup (optional, recommended!)

```bash
./cleanup-expired.sh
```

This script deletes servers whose TTL labels have expired.
It can be scheduled via cron for automatic cleanup.

Simply run command

```bash
crontab -e
```

And add the following line at the end:

```bash
*/30 * * * * (INSERT_PATH_TO_PROJECT_HERE)/cleanup-expired.sh >> (INSERT_PATH_TO_PROJECT_HERE)/cleanup.log 2>&1
```