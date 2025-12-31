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

.PHONY: up down status ip ssh deploy logs labels $(CLOUD_INIT) volume-create volume-attach volume-detach

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
		"cd ~/src && docker compose -f docker-compose.prod.yml up -d"

stop-prod: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	echo "Stopping production services on $$IP..."; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.prod.yml down"

logs-prod: validate
	@IP=$$(hcloud server list -o noheader -o columns=name,ipv4 | awk '$$1=="$(SERVER_NAME)" {print $$2}'); \
	if [ -z "$$IP" ]; then \
		echo "Server $(SERVER_NAME) not found"; \
		exit 1; \
	fi; \
	ssh -i $(SSH_IDENTITY) -o StrictHostKeyChecking=no ubuntu@$$IP \
		"cd ~/src && docker compose -f docker-compose.prod.yml logs -f"
