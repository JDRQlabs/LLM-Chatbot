#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions for colored output
error() {
  echo -e "${RED}✗ Error: $1${NC}" >&2
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

info() {
  echo -e "${YELLOW}ℹ $1${NC}"
}

# 1. Load environment variables from the .env file in parent directory
load_env() {
  # Get the directory where this script is located
  local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # .env should be in the parent of the script's directory (src/.env)
  local env_file="${script_dir}/../.env"
  
  if [ ! -f "$env_file" ]; then
    error ".env file not found at: $env_file"
    echo "  Expected location: $(dirname "$script_dir")/.env"
    exit 1
  fi
  
  # Use a more robust method: set -a enables automatic export
  # Filter out comments and empty lines, then source
  set -a
  # Create a temporary file with cleaned .env content
  local temp_env=$(mktemp)
  grep -v '^[[:space:]]*#' "$env_file" | grep -v '^[[:space:]]*$' > "$temp_env"
  
  # Source the cleaned .env file
  # This properly handles quoted values, spaces, and special characters
  . "$temp_env" 2>/dev/null || {
    # Fallback: read line by line if sourcing fails
    while IFS= read -r line || [ -n "$line" ]; do
      [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
      # Remove inline comments (simple approach)
      line=$(echo "$line" | sed 's/[[:space:]]*#.*$//')
      [[ -z "$line" ]] && continue
      # Export the variable
      export "$line" 2>/dev/null || true
    done < "$env_file"
  }
  set +a
  rm -f "$temp_env"
  
  success ".env file loaded"
}

load_env

# Configuration (Matches your Docker Compose service & env var names)
CONTAINER_NAME="business_logic_db" #must match the container name in the docker-compose.yml file
DB_USER="$BUSINESS_LOGIC_DB_USER"
DB_NAME="$BUSINESS_LOGIC_DB_NAME"

# Validate configuration
if [ -z "$DB_USER" ] || [ -z "$DB_NAME" ]; then
  error "Database configuration missing in .env file:"
  [ -z "$DB_USER" ] && echo "  - BUSINESS_LOGIC_DB_USER"
  [ -z "$DB_NAME" ] && echo "  - BUSINESS_LOGIC_DB_NAME"
  echo ""
  info "Debug: Checking loaded environment variables..."
  echo "  BUSINESS_LOGIC_DB_USER=${BUSINESS_LOGIC_DB_USER:-<not set>}"
  echo "  BUSINESS_LOGIC_DB_NAME=${BUSINESS_LOGIC_DB_NAME:-<not set>}"
  echo ""
  echo "  All variables containing 'DB' or 'BUSINESS':"
  env | grep -iE "(DB|BUSINESS)" | sed 's/^/    /' || echo "    (none found)"
  exit 1
fi

# Check if container exists and is running
check_container() {
  if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    error "Container '${CONTAINER_NAME}' is not running."
    echo "  Please start it with: docker-compose up -d ${CONTAINER_NAME}"
    exit 1
  fi
  success "Container '${CONTAINER_NAME}' is running"
}

# Check if SQL file exists
check_file() {
  local file=$1
  if [ ! -f "$file" ]; then
    error "SQL file not found: $file"
    exit 1
  fi
}

# Helper function to run SQL inside the Docker container
run_sql() {
  local file=$1
  local temp_output
  local exit_code=0
  
  check_file "$file"
  
  info "Running $file..."
  
  # Capture output and exit code
  # For seed.sql, use envsubst to replace environment variables
  # For other files, just cat the file
  if [ "$file" = "seed.sql" ]; then
    temp_output=$(envsubst < "$file" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" 2>&1)
    exit_code=$?
  else
    temp_output=$(cat "$file" | docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" 2>&1)
    exit_code=$?
  fi
  
  if [ $exit_code -eq 0 ]; then
    success "$file executed successfully"
    return 0
  else
    error "$file failed with exit code $exit_code"
    # Show relevant error messages (filter out noise)
    local error_lines=$(echo "$temp_output" | grep -iE "error|fatal|failed|syntax|does not exist" | head -3)
    if [ -n "$error_lines" ]; then
      echo ""
      echo "Error details:"
      echo "$error_lines" | sed 's/^/  /'
    fi
    echo ""
    echo "  Troubleshooting:"
    echo "  - Check SQL syntax in $file"
    echo "  - Verify database connection and credentials"
    echo "  - Ensure container '$CONTAINER_NAME' is running"
    return $exit_code
  fi
}

# Apply database migrations
run_migrations() {
  local migrations_dir="migrations"

  info "Applying database migrations..."

  # Check if migrations directory exists
  if [ ! -d "$migrations_dir" ]; then
    error "Migrations directory not found: $migrations_dir"
    return 1
  fi

  # Get list of migration files in sorted order
  local migration_files=$(ls "$migrations_dir"/*.sql 2>/dev/null | sort)

  if [ -z "$migration_files" ]; then
    info "No migration files found in $migrations_dir/"
    return 0
  fi

  # Apply each migration file
  local migration_count=0
  for migration_file in $migration_files; do
    local migration_name=$(basename "$migration_file")
    info "  Applying migration: $migration_name"

    if ! run_sql "$migration_file"; then
      error "Migration failed: $migration_name"
      return 1
    fi

    migration_count=$((migration_count + 1))
  done

  success "Applied $migration_count migration(s)"
  return 0
}

# Validate required environment variables for seed.sql
validate_seed_vars() {
  if [ -z "$WHATSAPP_PHONE_NUMBER_ID" ] || [ -z "$WHATSAPP_ACCESS_TOKEN" ]; then
    error "Required environment variables not set in .env file:"
    [ -z "$WHATSAPP_PHONE_NUMBER_ID" ] && echo "  - WHATSAPP_PHONE_NUMBER_ID"
    [ -z "$WHATSAPP_ACCESS_TOKEN" ] && echo "  - WHATSAPP_ACCESS_TOKEN"
    echo ""
    echo "Please add these to your .env file:"
    echo "  WHATSAPP_PHONE_NUMBER_ID=your_phone_id"
    echo "  WHATSAPP_ACCESS_TOKEN=your_access_token"
    exit 1
  fi
  success "Required environment variables validated"
}

# Verify database tables and their contents
verify_db() {
  info "Verifying database '$DB_NAME'..."
  echo ""
  
  # Get list of tables
  local tables=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY tablename;
  " 2>/dev/null | grep -v '^$')
  
  if [ -z "$tables" ]; then
    error "No tables found in database '$DB_NAME'"
    echo "  Run './manage_db.sh create' to create the schema"
    return 1
  fi
  
  local table_count=$(echo "$tables" | wc -l)
  success "Found $table_count table(s)"
  echo ""
  
  # For each table, show structure and contents
  for table in $tables; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    info "Table: $table"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get row count
    local count=$(docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -A -c "
      SELECT COUNT(*) FROM \"$table\";
    " 2>/dev/null | tr -d ' ')
    
    echo "Row count: $count"
    echo ""
    
    # Show table structure (column names and types)
    echo "Schema:"
    docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
      SELECT 
        column_name AS \"Column\",
        data_type AS \"Type\",
        CASE 
          WHEN character_maximum_length IS NOT NULL 
          THEN data_type || '(' || character_maximum_length || ')'
          ELSE data_type
        END AS \"Full Type\",
        is_nullable AS \"Nullable\"
      FROM information_schema.columns
      WHERE table_name = '$table'
      ORDER BY ordinal_position;
    " 2>/dev/null
    
    echo ""
    
    # Show sample data (limit to 3 rows for readability)
    if [ "$count" -gt 0 ]; then
      local display_rows=3
      if [ "$count" -lt "$display_rows" ]; then
        display_rows=$count
      fi
      echo "Sample data (showing $display_rows of $count rows):"
      docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
        SELECT * FROM \"$table\" LIMIT $display_rows;
      " 2>/dev/null
    else
      echo "No data in this table"
    fi
    
    echo ""
    echo ""
  done
  
  success "Verification complete"
  return 0
}

# 2. Command Router
case "$1" in
  "drop")
    check_container
    info "WARNING: This will delete all data in database '$DB_NAME'."
    read -p "Are you sure? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      if run_sql "drop.sql"; then
        success "Database '$DB_NAME' dropped successfully"
      else
        error "Failed to drop database"
        exit 1
      fi
    else
      info "Operation cancelled"
    fi
    ;;
  
  "create")
    check_container
    if ! run_sql "create.sql"; then
      error "Failed to create schema"
      exit 1
    fi

    if ! run_migrations; then
      error "Failed to apply migrations"
      exit 1
    fi

    success "Schema and migrations applied successfully in database '$DB_NAME'"
    ;;
  
  "seed")
    check_container
    validate_seed_vars
    if run_sql "seed.sql"; then
      success "Seed data inserted successfully into database '$DB_NAME'"
    else
      error "Failed to insert seed data"
      exit 1
    fi
    ;;
  
  "reset")
    check_container
    validate_seed_vars
    info "Resetting database '$DB_NAME' (drop -> create -> migrations -> seed)..."

    if ! run_sql "drop.sql"; then
      error "Failed to drop database. Aborting reset."
      exit 1
    fi

    if ! run_sql "create.sql"; then
      error "Failed to create schema. Aborting reset."
      exit 1
    fi

    if ! run_migrations; then
      error "Failed to apply migrations. Aborting reset."
      exit 1
    fi

    if ! run_sql "seed.sql"; then
      error "Failed to insert seed data. Aborting reset."
      exit 1
    fi

    success "Database reset complete!"
    ;;
  
  "verify")
    check_container
    if verify_db; then
      success "Database verification completed successfully"
    else
      error "Database verification failed"
      exit 1
    fi
    ;;
  
  *)
    error "Invalid command: $1"
    echo ""
    echo "Usage: ./manage_db.sh [create | seed | drop | reset | verify]"
    echo ""
    echo "Commands:"
    echo "  create  - Create database schema"
    echo "  seed    - Insert seed data (requires WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN in .env)"
    echo "  drop    - Drop all tables (with confirmation)"
    echo "  reset   - Drop, create, and seed database (full reset)"
    echo "  verify  - Show all tables, their structure, and sample data"
    exit 1
    ;;
esac