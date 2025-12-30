# Database Scaling Strategy

This document outlines the path for scaling FastBots.ai from MVP to production at scale.

## Current Architecture (MVP)

**Database:** Custom PostgreSQL 16 with pgvector (Docker container)
**Storage:** Docker volume (`business_logic_db_data`)
**Capacity:** ~1-100 users
**Cost:** €0 (local development)

### Characteristics
- ✅ Fast development iteration
- ✅ Full control over configuration
- ✅ Zero external dependencies
- ❌ Single point of failure
- ❌ Manual backups required
- ❌ Limited to single server

---

## Phase 1: Production Deploy (1-100 Users)

**Timeline:** Week 1
**Target:** Initial production deployment on Hetzner

### Infrastructure
- **Server:** Hetzner CPX21 (3 vCPU, 4GB RAM, 80GB SSD) - €6.90/month
- **Database:** Same Docker container, but with **Hetzner Block Storage**
- **Backup:** Automated daily snapshots to Hetzner Object Storage

### Migration Steps

1. **Attach Block Storage Volume** (20GB, €2.40/month):
   ```bash
   # On Hetzner Cloud Console:
   # Create volume: fastbots-db-volume (20GB, ext4)
   # Attach to server, mount at /mnt/db-storage

   # Update docker-compose.yml:
   volumes:
     business_logic_db_data:
       driver: local
       driver_opts:
         type: none
         o: bind
         device: /mnt/db-storage
   ```

2. **Setup Automated Backups**:
   ```bash
   # Create backup script: /usr/local/bin/backup-db.sh
   #!/bin/bash
   DATE=$(date +%Y%m%d_%H%M%S)
   docker exec business_logic_db pg_dump -U business_logic_user business_logic_app \
     | gzip > /tmp/backup_${DATE}.sql.gz

   # Upload to Hetzner Object Storage (S3-compatible)
   s3cmd put /tmp/backup_${DATE}.sql.gz \
     s3://fastbots-backups/db/backup_${DATE}.sql.gz

   # Cleanup old backups (keep 30 days)
   s3cmd ls s3://fastbots-backups/db/ | \
     awk '{print $4}' | \
     sort | \
     head -n -30 | \
     xargs -I {} s3cmd del {}

   # Add to crontab:
   0 2 * * * /usr/local/bin/backup-db.sh
   ```

3. **Test Restore Procedure**:
   ```bash
   # Download latest backup
   s3cmd get s3://fastbots-backups/db/backup_latest.sql.gz

   # Restore to test database
   gunzip backup_latest.sql.gz
   docker exec -i business_logic_db psql -U business_logic_user business_logic_app \
     < backup_latest.sql
   ```

### Benefits
- ✅ Database volume can be detached and reattached to new servers
- ✅ Automated backups with 30-day retention
- ✅ Point-in-time recovery
- ✅ Easy vertical scaling (upgrade server, reattach volume)

### Limitations
- ❌ Still single server (downtime during upgrades)
- ❌ No read replicas
- ❌ Manual intervention for scaling

**Estimated Cost:** €9.30/month (server + block storage)

---

## Phase 2: Managed Database (100-1000 Users)

**Timeline:** Month 2-3
**Target:** Zero-downtime deployments, better reliability

### Infrastructure
- **App Server:** Hetzner CPX21 (3 vCPU, 4GB RAM) - €6.90/month
- **Database:** Hetzner Managed PostgreSQL (2 vCPU, 4GB RAM) - €39/month
- **Redis:** Hetzner Managed Redis (256MB) - €4/month

### Migration Steps

1. **Provision Managed Database**:
   ```bash
   # Via Hetzner Cloud Console:
   # Create Managed Database: PostgreSQL 16
   # Plan: Small (2 vCPU, 4GB RAM)
   # Enable automated backups (included)
   # Enable pgvector extension
   ```

2. **Zero-Downtime Migration**:
   ```bash
   # 1. Setup replication from Docker DB to Managed DB
   docker exec business_logic_db pg_dump -U business_logic_user \
     business_logic_app | \
     psql -h managed-db.hetzner.cloud -U business_logic_user \
     business_logic_app

   # 2. Switch application to managed DB (update .env)
   DB_HOST=managed-db.hetzner.cloud

   # 3. Restart application
   docker-compose restart fastbots_api webhook-ingress

   # 4. Verify data consistency
   # 5. Decomission Docker database container
   ```

3. **Enable Connection Pooling**:
   ```yaml
   # Use PgBouncer (included with Hetzner Managed DB)
   # Update connection string:
   DATABASE_URL=postgres://user:pass@managed-db.hetzner.cloud:6432/db?pool_timeout=10
   ```

### Benefits
- ✅ Automated backups with point-in-time recovery
- ✅ High availability (99.95% SLA)
- ✅ Automatic minor version upgrades
- ✅ Connection pooling included
- ✅ Monitoring dashboards included
- ✅ Zero-downtime scaling (vertical)

### Limitations
- ❌ Higher cost
- ❌ Less control over configuration
- ❌ Still single region

**Estimated Cost:** €49.90/month

---

## Phase 3: Read Replicas (1000-5000 Users)

**Timeline:** Month 4-6
**Target:** Improved read performance for RAG queries

### Infrastructure
- **App Servers:** 2x Hetzner CPX21 (load balanced) - €13.80/month
- **Load Balancer:** Hetzner Load Balancer - €5.90/month
- **Database:** Hetzner Managed PostgreSQL with 1 Read Replica - €78/month (primary + replica)
- **Redis:** Hetzner Managed Redis (1GB) - €10/month

### Implementation

1. **Add Read Replica**:
   ```bash
   # Via Hetzner Console: Add read replica to existing database
   # Replica will be in same data center
   # Replication lag typically <100ms
   ```

2. **Route Read Queries to Replica**:
   ```javascript
   // In api-server/routes/knowledge.js
   // Use read replica for RAG search queries
   const readPool = new Pool({
     host: process.env.DB_READ_HOST || process.env.DB_HOST,
     port: process.env.DB_PORT,
     // ... other config
   });

   // Write operations use primary
   const writePool = new Pool({
     host: process.env.DB_HOST,
     // ...
   });

   // Example: RAG search uses read replica
   router.post('/:id/knowledge/search', async (req, res) => {
     const result = await readPool.query(`
       SELECT * FROM document_chunks
       WHERE chatbot_id = $1
       ORDER BY embedding <-> $2
       LIMIT 5
     `, [chatbotId, embedding]);
   });
   ```

3. **Load Balancer Configuration**:
   ```yaml
   # Hetzner Load Balancer
   algorithm: round_robin
   health_check:
     protocol: http
     port: 4000
     path: /health
     interval: 10s
   targets:
     - server: app-server-1 (10.0.0.2)
     - server: app-server-2 (10.0.0.3)
   ```

### Benefits
- ✅ Read queries don't impact write performance
- ✅ Horizontal read scalability
- ✅ Improved RAG search latency
- ✅ Better resource utilization

### Limitations
- ❌ Replication lag (eventual consistency)
- ❌ More complex application logic
- ❌ Higher costs

**Estimated Cost:** €107.70/month

---

## Phase 4: Sharding (5000-20000 Users)

**Timeline:** Month 7-12
**Target:** Horizontal write scalability

### Architecture
```
                     Load Balancer
                          |
      +-------------------+-------------------+
      |                   |                   |
  App Server 1       App Server 2       App Server 3
      |                   |                   |
      +-------------------+-------------------+
                          |
                    Shard Router
                          |
      +-------------------+-------------------+
      |                   |                   |
    Shard 1             Shard 2             Shard 3
 (Org ID: 0-333)    (Org ID: 334-666)   (Org ID: 667-999)
```

### Sharding Strategy

**Shard Key:** `organization_id`
**Reason:** Each organization's data is isolated, natural partitioning

1. **Shard Routing Logic**:
   ```javascript
   function getShardForOrganization(organizationId) {
     const hash = crypto.createHash('md5')
       .update(organizationId)
       .digest('hex');
     const shardNumber = parseInt(hash.slice(0, 8), 16) % NUM_SHARDS;
     return SHARD_POOLS[shardNumber];
   }

   // Usage
   const pool = getShardForOrganization(orgId);
   const result = await pool.query('SELECT ...');
   ```

2. **Cross-Shard Queries**:
   ```javascript
   // For admin queries spanning all organizations
   async function getAllOrganizations() {
     const results = await Promise.all(
       SHARD_POOLS.map(pool =>
         pool.query('SELECT * FROM organizations')
       )
     );
     return results.flat();
   }
   ```

### Migration to Sharded Architecture

**CRITICAL:** This is complex and requires significant planning. Consider using:
- Vitess (open-source sharding solution)
- Citus (PostgreSQL extension for sharding)
- Manual sharding with routing layer

**Estimated Cost:** €300-500/month (3 sharded databases + infrastructure)

---

## Phase 5: Multi-Region (20000+ Users)

**Timeline:** Year 2
**Target:** Global performance, disaster recovery

### Architecture
```
                        Global Load Balancer
                     (GeoDNS / Cloudflare)
                                |
                +---------------+---------------+
                |                               |
           EU Region                       US Region
                |                               |
        Hetzner Falkenstein             Hetzner Ashburn
        - App Servers (3x)              - App Servers (3x)
        - PostgreSQL Primary            - PostgreSQL Replica
        - Redis Cluster                 - Redis Cluster
```

### Implementation
- **Multi-region read replicas** for low-latency reads
- **Global write coordination** via primary in EU
- **CDN** for static assets (Cloudflare)
- **Cross-region backup replication**

**Estimated Cost:** €800-1200/month

---

## Decision Matrix

| User Count | Phase | Monthly Cost | Complexity | Recommended |
|------------|-------|--------------|------------|-------------|
| 1-100 | Phase 1: Block Storage | €9 | Low | ✅ Start here |
| 100-1000 | Phase 2: Managed DB | €50 | Medium | ✅ Production ready |
| 1000-5000 | Phase 3: Read Replicas | €108 | Medium | Optional |
| 5000-20000 | Phase 4: Sharding | €300-500 | High | As needed |
| 20000+ | Phase 5: Multi-Region | €800-1200 | Very High | Enterprise |

---

## Vector Database Considerations

**Current:** pgvector in PostgreSQL (works well up to ~1M vectors)

**When to migrate to dedicated vector DB:**

### Triggers for Migration:
1. **>1M document chunks** stored
2. **Search latency >200ms** consistently
3. **Complex embedding operations** (re-ranking, hybrid search)

### Options:
1. **Qdrant** (open-source, self-hosted)
   - Cost: €20-50/month (small instance)
   - Benefits: Purpose-built for vectors, better performance

2. **Weaviate** (open-source, self-hosted)
   - Cost: €30-60/month
   - Benefits: GraphQL API, hybrid search built-in

3. **Pinecone** (managed, cloud)
   - Cost: $70-140/month (production tier)
   - Benefits: Fully managed, excellent performance

**Recommendation:** Stay with pgvector until Phase 3, then evaluate Qdrant

---

## Backup Strategy

### Phase 1-2: Daily Backups
- Frequency: Daily at 2 AM UTC
- Retention: 30 days
- Storage: Hetzner Object Storage
- Cost: ~€1/month

### Phase 3+: Continuous Backups
- Frequency: Continuous WAL archiving
- Point-in-time recovery: Any point in last 7 days
- Storage: S3-compatible object storage
- Cost: ~€5/month

### Disaster Recovery Testing
- **Monthly:** Restore backup to test environment
- **Quarterly:** Full DR drill (simulate complete failure)
- **SLA Target:** RPO < 1 hour, RTO < 4 hours

---

## Monitoring & Alerting

### Key Metrics to Monitor:
1. **Database CPU/Memory** usage
2. **Query latency** (p50, p95, p99)
3. **Connection pool** utilization
4. **Disk I/O** and storage usage
5. **Replication lag** (if using replicas)
6. **Backup success/failure** rate

### Alert Thresholds:
- **CPU > 80%** for 5 minutes → Scale up
- **Disk > 85%** → Expand storage
- **Query latency p95 > 500ms** → Optimize queries
- **Backup failure** → Immediate investigation

---

## Cost Optimization Tips

1. **Right-size instances:** Don't over-provision early
2. **Use spot instances** for non-critical workers (Hetzner doesn't have spot, but can use smaller instances)
3. **Archive old data:** Move >90 day old messages to cold storage
4. **Compress backups:** gzip reduces storage by ~70%
5. **Monitor query performance:** Optimize slow queries before scaling hardware
6. **Connection pooling:** Reduce database connections (saves memory)

---

## Summary

Start simple (Phase 1), migrate to managed database when hitting 100 users (Phase 2), add read replicas when RAG performance degrades (Phase 3). Only consider sharding (Phase 4) if you reach 5000+ users.

**Key Principle:** Vertical scaling is cheaper and simpler than horizontal scaling until you absolutely need it.

**Next Steps:**
1. Implement Phase 1 (Block Storage) on production server
2. Setup automated backups
3. Document restore procedure
4. Test monthly backup restores
5. Plan Phase 2 migration when approaching 100 users
