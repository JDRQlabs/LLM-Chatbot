#!/bin/bash
#
# Database Restore Script for WhatsApp Chatbot Platform
#
# Usage:
#   ./restore_db.sh backup_20240101_020000.sql.gz
#   ./restore_db.sh --list                          # List available backups
#   ./restore_db.sh --latest                        # Restore from latest backup
#
# WARNING: This will DROP and recreate the database!
#
# Environment Variables:
#   BACKUP_DIR          - Directory containing backups (default: /mnt/data/backups)
#   POSTGRES_CONTAINER  - Docker container name (default: db)

set -euo pipefail

# Configuration with defaults
BACKUP_DIR="${BACKUP_DIR:-/mnt/data/backups}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-db}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log_success() {
    log "${GREEN}SUCCESS:${NC} $1"
}

log_warning() {
    log "${YELLOW}WARNING:${NC} $1"
}

log_error() {
    log "${RED}ERROR:${NC} $1"
}

list_backups() {
    log "Available backups in ${BACKUP_DIR}:"
    echo ""
    ls -lh "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null | while read -r line; do
        echo "  $line"
    done || echo "  No backups found."
    echo ""
}

get_latest_backup() {
    ls -t "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null | head -1
}

verify_checksum() {
    local backup_file="$1"
    local checksum_file="${backup_file}.sha256"

    if [ -f "${checksum_file}" ]; then
        log "Verifying checksum..."
        if sha256sum -c "${checksum_file}" > /dev/null 2>&1; then
            log_success "Checksum verified"
            return 0
        else
            log_error "Checksum verification failed!"
            return 1
        fi
    else
        log_warning "No checksum file found, skipping verification"
        return 0
    fi
}

# Parse arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.sql.gz> | --list | --latest"
    echo ""
    list_backups
    exit 1
fi

case "$1" in
    --list)
        list_backups
        exit 0
        ;;
    --latest)
        BACKUP_FILE=$(get_latest_backup)
        if [ -z "${BACKUP_FILE}" ]; then
            log_error "No backups found in ${BACKUP_DIR}"
            exit 1
        fi
        log "Using latest backup: ${BACKUP_FILE}"
        ;;
    *)
        if [ -f "${BACKUP_DIR}/$1" ]; then
            BACKUP_FILE="${BACKUP_DIR}/$1"
        elif [ -f "$1" ]; then
            BACKUP_FILE="$1"
        else
            log_error "Backup file not found: $1"
            list_backups
            exit 1
        fi
        ;;
esac

# Safety confirmation
log_warning "This will DROP and recreate the database!"
log_warning "Backup file: ${BACKUP_FILE}"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm
if [ "$confirm" != "yes" ]; then
    log "Restore cancelled."
    exit 0
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    log_error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running!"
    exit 1
fi

# Verify checksum
verify_checksum "${BACKUP_FILE}" || exit 1

# Get database connection info
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-windmill}"

log "Starting database restore..."
log "Target database: ${DB_NAME}"

# Stop dependent services (optional)
log_warning "Consider stopping dependent services before restore"

# Create restore
START_TIME=$(date +%s)

log "Dropping and recreating database..."
docker exec "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" -c "DROP DATABASE IF EXISTS ${DB_NAME};"
docker exec "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" -c "CREATE DATABASE ${DB_NAME};"

log "Restoring from backup..."
if gunzip -c "${BACKUP_FILE}" | docker exec -i "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" "${DB_NAME}"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_success "Restore completed in ${DURATION}s"

    # Verify restore
    log "Verifying restore..."
    TABLE_COUNT=$(docker exec "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" "${DB_NAME}" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    log "Tables restored: ${TABLE_COUNT}"

    log_success "Database restore completed successfully!"
else
    log_error "Restore failed!"
    exit 1
fi

log_warning "Remember to restart dependent services"

exit 0
