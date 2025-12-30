# Development Workflow

## Database Schema Changes

**CRITICAL:** Whenever you modify the database schema (create.sql, seed.sql), you MUST:

1. **Reset the database:**
   ```bash
   ./db/manage_db.sh reset
   ```

2. **Verify your changes:**
   - Check that all new tables/columns exist
   - Verify triggers are created
   - Confirm seed data loaded correctly
   - Test any new database functions

3. **Common verification queries:**
   ```sql
   -- List all tables
   \dt

   -- Describe a table
   \d table_name

   -- List all triggers
   SELECT trigger_name, event_manipulation, event_object_table
   FROM information_schema.triggers;

   -- List all extensions
   SELECT * FROM pg_extension;
   ```

## Windmill Script Changes

After creating or modifying scripts:

1. **Generate metadata:**
   ```bash
   wmill script generate-metadata
   ```

2. **For flow inline scripts:**
   ```bash
   wmill flow generate-locks --yes
   ```

3. **Push to Windmill (if needed):**
   ```bash
   wmill sync push
   ```

## Docker Container Changes

When modifying Dockerfiles or docker-compose.yml:

1. **Rebuild specific service:**
   ```bash
   docker-compose up --build service_name
   ```

2. **Rebuild all:**
   ```bash
   docker-compose up --build
   ```

3. **Clean rebuild (remove volumes):**
   ```bash
   docker-compose down -v
   docker-compose up --build
   ```

## Git Workflow

### Commit Frequency
- Commit after completing each logical unit of work
- Commit after database schema changes
- Commit after creating new files/components
- Commit after successful test runs
- Commit after completing each task within a phase

### Commit Message Format
```
[Phase X.Y] Brief description

Detailed changes:
- What was added/modified
- Why the change was made
- Any related files

Technical details:
- Implementation notes
- Breaking changes
- Migration notes

Issue: #N/A (or issue number)
```

### Branch Strategy
```
master (production-ready code)
  └── feature/rag-knowledge-base (main development branch)
       ├── feature/rag-plan-limits (Phase 1)
       ├── feature/rag-web-crawler (Phase 2)
       └── ... (other phase branches)
```

## Testing Workflow

### After Database Changes
1. Reset database: `./db/manage_db.sh reset`
2. Verify schema changes with SQL queries
3. Test seed data loaded correctly
4. Run integration tests

### After API Changes
1. Rebuild API container
2. Test health endpoint: `curl http://localhost:4000/health`
3. Test each modified endpoint with curl
4. Verify error handling

### After Windmill Script Changes
1. Generate metadata
2. Test script execution via Windmill UI or CLI
3. Verify error handling
4. Check logs for issues

## Pre-Commit Checklist

- [ ] Database changes verified with `./db/manage_db.sh reset`
- [ ] Windmill metadata generated
- [ ] Docker containers build successfully
- [ ] No syntax errors in code
- [ ] No secrets in committed files
- [ ] Tests passing
- [ ] Documentation updated

## Common Issues

### Database Connection Failed
**Cause:** Database container not running or wrong credentials
**Solution:**
```bash
docker-compose ps
docker-compose logs business_logic_db
```

### Windmill Script Not Found
**Cause:** Metadata not generated or script not synced
**Solution:**
```bash
wmill script generate-metadata
wmill sync push
```

### Docker Build Fails
**Cause:** Missing dependencies or syntax errors in Dockerfile
**Solution:**
- Check Dockerfile syntax
- Review build logs
- Try clean rebuild: `docker-compose down && docker-compose up --build`

### npm ci Fails
**Cause:** Missing package-lock.json
**Solution:** Use `npm install --production` instead of `npm ci`
