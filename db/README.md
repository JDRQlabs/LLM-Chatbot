# Database Setup Guide

This directory contains the database schema and seed data for the FastBots Clone MVP.

## Prerequisites

1. Ensure Docker Compose is running and the PostgreSQL database container is up:
   ```bash
   docker-compose ps
   ```

2. Verify the database service is healthy:
   ```bash
   docker-compose logs db
   ```

## Database Connection Details

The PostgreSQL database is configured in `docker-compose.yml` with the following settings:
- **Database Name:** `windmill`
- **Username:** `postgres`
- **Password:** `changeme`
- **Host:** `db` (when connecting from within Docker network)
- **Port:** `5432`

## Running the Scripts

### Option 1: Using manage_db.sh (Recommended for business_logic_db)

If you're using the `business_logic_db` container, you can use the `manage_db.sh` script which automatically loads environment variables from your `.env` file.

#### Prerequisites

1. Ensure your `.env` file contains the required WhatsApp credentials:
   ```bash
   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
   WHATSAPP_ACCESS_TOKEN=your_meta_access_token
   OWNER_EMAIL=your_email
   ```

2. Make sure `manage_db.sh` is executable:
   ```bash
   chmod +x db/manage_db.sh
   ```

3. Make sure your current working directory is set to /src/db/ prior to script execution, or it may fail

#### Usage

From the `db/` directory:

```bash
# Create schema
./manage_db.sh create

# Seed data (requires WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN in .env)
./manage_db.sh seed

# Reset everything (drop, create, seed)
./manage_db.sh reset

# Drop all tables (with confirmation)
./manage_db.sh drop
```

**Note:** The `seed` and `reset` commands will automatically substitute `${WHATSAPP_PHONE_NUMBER_ID}` and `${WHATSAPP_ACCESS_TOKEN}` placeholders in `seed.sql` with values from your `.env` file.

## Verifying the Setup

After running both scripts, verify the tables were created:

```bash
docker-compose exec db psql -U postgres -d windmill -c "\dt"
```

You should see tables like:
- `organizations`
- `users`
- `org_integrations`
- `chatbots`
- `chatbot_integrations`
- `knowledge_sources`
- `contacts`
- `messages`

To verify seed data was inserted:

```bash
docker-compose exec db psql -U postgres -d windmill -c "SELECT * FROM organizations;"
docker-compose exec db psql -U postgres -d windmill -c "SELECT * FROM chatbots;"
```

## Troubleshooting

### Database Container Not Running

If the database container is not running:

```bash
docker-compose up -d db
```

Wait for the health check to pass (usually 10-30 seconds).

### Permission Errors

If you encounter permission errors, ensure you're using the correct username (`postgres`) and that the database container has the proper volumes mounted.

### Connection Refused

If you get connection refused errors:
1. Check that the database container is healthy: `docker-compose ps`
2. Check database logs: `docker-compose logs db`
3. Ensure the database has finished initializing (wait for health check)

### Script Errors

If you encounter errors when running the scripts:
- Ensure `schema.sql` ran successfully before running `seed.sql`
- Check that the `pgcrypto` extension is available (it should be in PostgreSQL 16)
- Verify the SQL syntax is correct for your PostgreSQL version

## Next Steps

After setting up the database:

1. **If using `manage_db.sh`:** Ensure your `.env` file contains `WHATSAPP_PHONE_NUMBER_ID` and `WHATSAPP_ACCESS_TOKEN` before running the seed command.

2. **If using Docker exec directly:** You'll need to manually edit `seed.sql` to replace the `${WHATSAPP_PHONE_NUMBER_ID}` and `${WHATSAPP_ACCESS_TOKEN}` placeholders, or use `envsubst`:
   ```bash
   envsubst < db/seed.sql | docker-compose exec -T db psql -U postgres -d windmill
   ```

3. Configure your Windmill flows to use the database connection.

4. Test the webhook integration to ensure data flows correctly.

