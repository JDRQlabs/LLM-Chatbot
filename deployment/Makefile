# load .env (from parent directory)
ifneq (,$(wildcard ../.env))
  include ../.env
  export
endif

# Also load local .env if exists
ifneq (,$(wildcard .env))
  include .env
  export
endif

# ---- Configurable variables ----
SERVER_NAME ?= whatsapp-chatbot-prod
SERVER_TYPE ?= cpx31  # 4 vCPU, 8GB RAM - recommended for Phase 0
IMAGE ?= ubuntu-22.04
LOCATION ?= nbg1
SSH_KEY_NAME ?= hetzner-proto
SSH_IDENTITY ?= $(HOME)/.ssh/hetzner-proto
TTL ?= 24h  # longer TTL for production server
CREATED_AT := $(shell date +%s)
LABELS := ttl=$(TTL),created_at=$(CREATED_AT),purpose=prod

# Hetzner Volume configuration (optional, set in .env)
# HETZNER_VOLUME_ID - numeric ID of your Hetzner volume (e.g., 12345678)
HETZNER_VOLUME_ID ?=
HETZNER_VOLUME_NAME ?= whatsapp-data

# Source directory (parent of deployment/)
SRC_DIR := $(shell cd .. && pwd)

# ---- Derived ----
SERVER_ID := $(shell hcloud server list -o noheader -o columns=id,name | awk '$$2=="$(SERVER_NAME)" {print $$1}')
VOLUME_ID := $(shell hcloud volume list -o noheader -o columns=id,name | awk '$$2=="$(HETZNER_VOLUME_NAME)" {print $$1}')
CLOUD_INIT := cloud-init.yaml

.PHONY: up down status ip ssh deploy logs labels $(CLOUD_INIT) volume-create volume-attach volume-detach volume-setup start-prod stop-prod logs-prod healthcheck db-init db-reset ps restart-service full-deploy create-admin setup-windmill help

# Always regenerate cloud-init.yaml to pick up .env changes
$(CLOUD_INIT):
	@echo "Generating cloud-init.yaml"
	@env SSH_PUBLIC_KEY="$$(cat $(SSH_IDENTITY).pub)" \
	  HETZNER_VOLUME_ID="$(HETZNER_VOLUME_ID)" \
	  envsubst < cloud-init.yaml.tmpl > $(CLOUD_INIT)

validate:
	@test -n "$(SERVER_NAME)" || (echo "SERVER_NAME not set" && exit 1)
	@test -f "$(SSH_IDENTITY)" || (echo "Missing SSH private key: $(SSH_IDENTITY)" && exit 1)
	@test -f "$(SSH_IDENTITY).pub" || (echo "Missing SSH public key: $(SSH_IDENTITY).pub" && exit 1)
	@command -v hcloud >/dev/null || (echo "hcloud CLI not installed" && exit 1)

# ---- Volume Management ----
volume-create:
	@if [ -n "$(VOLUME_ID)" ]; then \
		echo "Volume '$(HETZNER_VOLUME_NAME)' already exists (id=$(VOLUME_ID))"; \
	else \
		echo "Creating volume '$(HETZNER_VOLUME_NAME)' (10GB) in $(LOCATION)..."; \
		hcloud volume create \
			--name $(HETZNER_VOLUME_NAME) \
			--size 10 \
			--location $(LOCATION) \
			--format ext4; \
		echo "Volume created. Get the ID with: hcloud volume list"; \
	fi

volume-attach:
	@if [ -z "$(SERVER_ID)" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	if [ -z "$(VOLUME_ID)" ]; then \
		echo "Volume $(HETZNER_VOLUME_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Attaching volume $(VOLUME_ID) to server $(SERVER_ID)..."; \
	hcloud volume attach $(VOLUME_ID) --server $(SERVER_ID) --automount

volume-detach:
	@if [ -z "$(VOLUME_ID)" ]; then \
		echo "Volume $(HETZNER_VOLUME_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Detaching volume $(VOLUME_ID)..."; \
	hcloud volume detach $(VOLUME_ID)

volume-setup: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Setting up volume directories on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP '\
		set -e && \
		VOLUME_PATH=$$(ls -d /mnt/HC_Volume_* 2>/dev/null | head -1) && \
		if [ -z "$$VOLUME_PATH" ]; then echo "ERROR: No volume found"; exit 1; fi && \
		sudo ln -sf $$VOLUME_PATH /mnt/data && \
		sudo mkdir -p /mnt/data/postgres/windmill /mnt/data/postgres/business_logic /mnt/data/redis && \
		sudo chown -R 999:999 /mnt/data/postgres /mnt/data/redis && \
		sudo chmod -R 700 /mnt/data/postgres && \
		echo "Volume setup complete:" && ls -la /mnt/data/ \
	'

# ---- Server Management ----
up: validate $(CLOUD_INIT)
	@if [ -n "$(SERVER_ID)" ]; then \
		echo "Server already exists (id=$(SERVER_ID))"; \
	else \
		echo "Creating server $(SERVER_NAME) ($(SERVER_TYPE))"; \
		hcloud server create \
			--name $(SERVER_NAME) \
			--type $(SERVER_TYPE) \
			--image $(IMAGE) \
			--location $(LOCATION) \
			--ssh-key $(SSH_KEY_NAME) \
			--user-data-from-file $(CLOUD_INIT); \
		sleep 2; \
		ID=$$(hcloud server list -o noheader -o columns=id,name | awk '$$2=="$(SERVER_NAME)" {print $$1}'); \
		echo "Adding labels to server $$ID"; \
		hcloud server add-label $$ID ttl=$(TTL); \
		hcloud server add-label $$ID created_at=$(CREATED_AT); \
		hcloud server add-label $$ID purpose=prod; \
		echo ""; \
		echo "Server created. Next steps:"; \
		echo "  1. Wait ~2 minutes for cloud-init to complete"; \
		echo "  2. Attach volume: make volume-attach"; \
		echo "  3. Deploy code: make deploy"; \
	fi

down:
	@if [ -z "$(SERVER_ID)" ]; then \
		echo "Server does not exist"; \
	else \
		echo "WARNING: This will delete server $(SERVER_NAME) (id=$(SERVER_ID))"; \
		read -p "Are you sure? (y/n) " confirm && [ "$$confirm" = "y" ] && \
		hcloud server delete $(SERVER_ID) || echo "Cancelled"; \
	fi

status:
	@echo "=== Servers ==="
	@hcloud server list
	@echo ""
	@echo "=== Volumes ==="
	@hcloud volume list

ip:
	@hcloud server list -o noheader -o columns=name,ipv4 | grep $(SERVER_NAME) || true

ssh: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Cleaning known_hosts entry for $$IP (if any)"; \
	ssh-keygen -f "$(HOME)/.ssh/known_hosts" -R "$$IP" >/dev/null 2>&1 || true; \
	echo "Connecting to ubuntu@$$IP"; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP

deploy: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Deploying $(SRC_DIR) to ubuntu@$$IP:~/src/"; \
	rsync -avz --delete \
		--exclude '.git' \
		--exclude 'node_modules' \
		--exclude '__pycache__' \
		--exclude '.pytest_cache' \
		--exclude '.coverage' \
		--exclude 'htmlcov' \
		--exclude '.benchmarks' \
		--exclude 'deployment/' \
		-e "ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no" \
		$(SRC_DIR)/ ubuntu@$$IP:~/src/

logs:
	@hcloud server describe $(SERVER_NAME) | sed -n '/Events:/,$$p'

labels:
	@hcloud server describe $(SERVER_NAME) | sed -n '/Labels:/,/^$$/p'

# ---- Production Helpers ----
start-prod: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Starting production services on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml up -d"

stop-prod: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Stopping production services on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml down"

logs-prod: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml logs -f"

# Health check for all services
healthcheck: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	WEBHOOK_VERIFY_TOKEN="$(WEBHOOK_VERIFY_TOKEN)" \
	WINDMILL_AUTH_USER="$(WINDMILL_AUTH_USER)" \
	WINDMILL_AUTH_PASS="$(WINDMILL_AUTH_PASS)" \
	./scripts/healthcheck.sh $$IP

# Initialize database schema, migrations, and seed data
# Matches local db/manage_db.sh behavior: create -> migrations -> seed
db-init: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Initializing database on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP '\
		cd ~/src && \
		echo "Creating schema..." && \
		docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} < db/create.sql && \
		echo "Applying migrations..." && \
		for f in db/migrations/*.sql; do \
			echo "  Applying $$(basename $$f)..."; \
			docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} < "$$f"; \
		done && \
		echo "Seeding data..." && \
		source .env && envsubst < db/seed.sql | docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} && \
		echo "Database initialized successfully!" \
	'

# Reset database (drop, create, migrations, seed)
# Matches local db/manage_db.sh reset behavior
db-reset: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "WARNING: This will DELETE all data in the database!"; \
	read -p "Are you sure? (y/n) " confirm && [ "$$confirm" = "y" ] && \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP '\
		cd ~/src && \
		echo "Dropping tables..." && \
		docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} < db/drop.sql && \
		echo "Creating schema..." && \
		docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} < db/create.sql && \
		echo "Applying migrations..." && \
		for f in db/migrations/*.sql; do \
			echo "  Applying $$(basename $$f)..."; \
			docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} < "$$f"; \
		done && \
		echo "Seeding data..." && \
		source .env && envsubst < db/seed.sql | docker exec -i business_logic_db psql -U $${BUSINESS_LOGIC_DB_USER:-business_logic_user} -d $${BUSINESS_LOGIC_DB_NAME:-business_logic_app} && \
		echo "Database reset complete!" \
	'

# Container status
ps: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# Restart a specific service (does NOT reload .env - use recreate-service for that)
restart-service: validate
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make restart-service SERVICE=<service_name>"; \
		echo "Available services: caddy, webhook-ingress, whatsapp_chatbot_api, windmill_server, windmill_worker, business_logic_db, redis"; \
		exit 1; \
	fi; \
	IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Restarting $(SERVICE) on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml restart $(SERVICE)"

# Recreate a specific service (reloads .env and rebuilds if needed)
recreate-service: validate
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make recreate-service SERVICE=<service_name>"; \
		echo "This recreates the container with fresh environment from .env"; \
		exit 1; \
	fi; \
	IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Recreating $(SERVICE) on $$IP (will reload .env)..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml up -d --force-recreate $(SERVICE)"

# Full deployment workflow
full-deploy: deploy volume-setup start-prod healthcheck
	@echo "Full deployment complete!"

# Create admin user (for Phase 0 - registration is disabled)
# Usage: make create-admin EMAIL=admin@example.com PASSWORD=secure-password ORG_NAME="My Organization"
create-admin: validate
	@if [ -z "$(EMAIL)" ] || [ -z "$(PASSWORD)" ]; then \
		echo "Usage: make create-admin EMAIL=admin@example.com PASSWORD=secure-password ORG_NAME=\"My Organization\""; \
		echo ""; \
		echo "Arguments:"; \
		echo "  EMAIL     - Admin email address (required)"; \
		echo "  PASSWORD  - Admin password, min 8 characters (required)"; \
		echo "  ORG_NAME  - Organization name (optional, defaults to 'Default Organization')"; \
		exit 1; \
	fi; \
	IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	ORG="$${ORG_NAME:-Default Organization}"; \
	echo "Creating admin user on $$IP..."; \
	echo "  Email: $(EMAIL)"; \
	echo "  Organization: $$ORG"; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP " \
		docker exec whatsapp_chatbot_api node -e \" \
			const bcrypt = require('bcrypt'); \
			const { Pool } = require('pg'); \
			const pool = new Pool({ \
				host: 'business_logic_db', \
				port: 5432, \
				user: process.env.DB_USER || 'business_logic_user', \
				password: process.env.DB_PASSWORD || 'business_logic_password', \
				database: process.env.DB_NAME || 'business_logic_app' \
			}); \
			async function createAdmin() { \
				const client = await pool.connect(); \
				try { \
					await client.query('BEGIN'); \
					const orgSlug = '$$ORG'.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 50) + '-' + Date.now().toString(36); \
					const org = await client.query('INSERT INTO organizations (name, slug, plan_tier, is_active) VALUES (\\\$$1, \\\$$2, \\\"pro\\\", TRUE) RETURNING id', ['$$ORG', orgSlug]); \
					const hash = await bcrypt.hash('$(PASSWORD)', 12); \
					await client.query('INSERT INTO users (organization_id, email, password_hash, full_name, role) VALUES (\\\$$1, \\\$$2, \\\$$3, \\\"Admin\\\", \\\"owner\\\")', [org.rows[0].id, '$(EMAIL)', hash]); \
					await client.query('INSERT INTO usage_summary (organization_id, current_period_messages, current_period_tokens, period_start, period_end) VALUES (\\\$$1, 0, 0, CURRENT_DATE, CURRENT_DATE + INTERVAL \\\"1 month\\\") ON CONFLICT DO NOTHING', [org.rows[0].id]); \
					await client.query('COMMIT'); \
					console.log('Admin user created successfully!'); \
					console.log('Organization ID:', org.rows[0].id); \
				} catch (err) { \
					await client.query('ROLLBACK'); \
					console.error('Error:', err.message); \
					process.exit(1); \
				} finally { \
					client.release(); \
					pool.end(); \
				} \
			} \
			createAdmin(); \
		\" \
	"

# Setup Windmill (create workspace, token, sync scripts)
# Run this after Windmill is healthy on a fresh deployment
# Usage: make setup-windmill
#
# Note: Caddy's basic_auth is configured to EXCLUDE /api/* paths, so Windmill's API
# is accessible without basic auth. The API is still protected by Windmill's own
# Bearer token authentication. Only the admin UI requires basic auth.
setup-windmill: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Setting up Windmill on $$IP..."; \
	echo "This will:"; \
	echo "  1. Create a 'production' workspace"; \
	echo "  2. Generate an API token"; \
	echo "  3. Sync scripts and flows"; \
	echo "  4. Update .env with generated credentials"; \
	echo ""; \
	WINDMILL_URL="https://windmill.$${DOMAIN:-jdsoftwarelabs.com}" \
	WORKSPACE_NAME="production" \
	WORKSPACE_ID="production" \
	SCRIPTS_DIR="$(SRC_DIR)" \
	./scripts/setup-windmill.sh; \
	echo ""; \
	echo "Syncing updated .env to server..."; \
	rsync -avz \
		-e "ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no" \
		$(SRC_DIR)/.env ubuntu@$$IP:~/src/.env; \
	echo ""; \
	echo "Restarting webhook-ingress to pick up new credentials..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.phase0.yml restart webhook-ingress"

# Show help
help:
	@echo "=== WhatsApp Chatbot Deployment Makefile ==="
	@echo ""
	@echo "Server Management:"
	@echo "  make up              - Create a new VM"
	@echo "  make down            - Delete the VM (with confirmation)"
	@echo "  make status          - Show server and volume status"
	@echo "  make ip              - Show server IP"
	@echo "  make ssh             - SSH into the server"
	@echo ""
	@echo "Volume Management:"
	@echo "  make volume-create   - Create persistent storage volume"
	@echo "  make volume-attach   - Attach volume to server"
	@echo "  make volume-setup    - Setup volume directories"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy          - Sync code to server"
	@echo "  make start-prod      - Start all services"
	@echo "  make stop-prod       - Stop all services"
	@echo "  make full-deploy     - Full deployment workflow"
	@echo ""
	@echo "Database:"
	@echo "  make db-init         - Initialize database schema"
	@echo "  make db-reset        - Reset database (destructive!)"
	@echo ""
	@echo "Admin & Setup:"
	@echo "  make create-admin    - Create admin user (EMAIL=... PASSWORD=...)"
	@echo "  make setup-windmill  - Setup Windmill workspace and sync flows"
	@echo ""
	@echo "Monitoring:"
	@echo "  make ps              - Show container status"
	@echo "  make logs-prod       - Tail production logs"
	@echo "  make healthcheck     - Run health checks"
	@echo "  make restart-service SERVICE=<name>  - Restart a service"
	@echo ""
	@echo "Fresh VM Setup Workflow:"
	@echo "  1. make volume-create     (one-time)"
	@echo "  2. make up"
	@echo "  3. make volume-attach"
	@echo "  4. make deploy"
	@echo "  5. make volume-setup"
	@echo "  6. make start-prod"
	@echo "  7. make db-init"
	@echo "  8. make setup-windmill"
	@echo "  9. make create-admin EMAIL=... PASSWORD=..."
	@echo ""
