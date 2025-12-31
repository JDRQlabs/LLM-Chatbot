#!/bin/bash
#
# Database Backup Script for WhatsApp Chatbot Platform
#
# Usage:
#   ./backup_db.sh                    # Full backup
#   ./backup_db.sh --incremental      # WAL-based incremental (requires WAL archiving)
#
# Environment Variables:
#   BACKUP_DIR          - Directory to store backups (default: /mnt/data/backups)
#   POSTGRES_CONTAINER  - Docker container name (default: db)
#   RETENTION_DAYS      - Number of days to keep backups (default: 7)
#   S3_BUCKET          - S3 bucket for remote backup (optional)
#   SLACK_WEBHOOK      - Slack webhook for notifications (optional)
#
# Recommended cron entry (daily at 2 AM UTC):
#   0 2 * * * /opt/whatsapp-chatbot/deployment/scripts/backup_db.sh >> /var/log/backup.log 2>&1

set -euo pipefail

# Configuration with defaults
BACKUP_DIR="${BACKUP_DIR:-/mnt/data/backups}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-db}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

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

notify_slack() {
    if [ -n "${SLACK_WEBHOOK:-}" ]; then
        local message="$1"
        local color="$2"
        curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"attachments\":[{\"color\":\"${color}\",\"text\":\"${message}\"}]}" \
            "${SLACK_WEBHOOK}" > /dev/null
    fi
}

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

log "Starting database backup..."
log "Backup directory: ${BACKUP_DIR}"
log "Container: ${POSTGRES_CONTAINER}"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${POSTGRES_CONTAINER}$"; then
    log_error "PostgreSQL container '${POSTGRES_CONTAINER}' is not running!"
    notify_slack "Database backup failed: Container not running" "danger"
    exit 1
fi

# Get database connection info from environment or container
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-windmill}"

log "Creating backup of database '${DB_NAME}'..."

# Create backup using pg_dump
START_TIME=$(date +%s)

if docker exec "${POSTGRES_CONTAINER}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_PATH}"; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)

    log_success "Backup completed in ${DURATION}s"
    log "Backup file: ${BACKUP_PATH}"
    log "Backup size: ${BACKUP_SIZE}"

    # Create checksum
    sha256sum "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"
    log "Checksum created: ${BACKUP_PATH}.sha256"

    # Upload to S3 if configured
    if [ -n "${S3_BUCKET:-}" ]; then
        log "Uploading to S3 bucket: ${S3_BUCKET}..."
        if aws s3 cp "${BACKUP_PATH}" "s3://${S3_BUCKET}/backups/${BACKUP_FILE}" && \
           aws s3 cp "${BACKUP_PATH}.sha256" "s3://${S3_BUCKET}/backups/${BACKUP_FILE}.sha256"; then
            log_success "Uploaded to S3 successfully"
        else
            log_warning "S3 upload failed, backup is still available locally"
        fi
    fi

    # Clean up old backups
    log "Cleaning up backups older than ${RETENTION_DAYS} days..."
    DELETED_COUNT=$(find "${BACKUP_DIR}" -name "backup_*.sql.gz*" -mtime +${RETENTION_DAYS} -delete -print | wc -l)
    log "Deleted ${DELETED_COUNT} old backup files"

    # Send success notification
    notify_slack "Database backup completed successfully. Size: ${BACKUP_SIZE}, Duration: ${DURATION}s" "good"

    log_success "Backup process completed successfully!"

else
    log_error "Backup failed!"
    notify_slack "Database backup FAILED! Check logs immediately." "danger"
    exit 1
fi

# List current backups
log "Current backups:"
ls -lh "${BACKUP_DIR}"/backup_*.sql.gz 2>/dev/null || log "No backups found"

# Show disk usage
DISK_USAGE=$(df -h "${BACKUP_DIR}" | tail -1 | awk '{print $5}')
log "Backup disk usage: ${DISK_USAGE}"

if [ "${DISK_USAGE%\%}" -gt 80 ]; then
    log_warning "Disk usage is above 80%! Consider cleaning up old backups or increasing storage."
    notify_slack "Warning: Backup disk usage is ${DISK_USAGE}" "warning"
fi

exit 0
