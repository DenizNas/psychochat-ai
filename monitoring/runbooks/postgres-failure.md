# Runbook: PostgreSQL Database Operational Failure

- **Severity Level**: SEV-1 (Critical)
- **Target Component**: `psychochat-postgres` StatefulSet Database
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Users cannot log in or register accounts due to persistent `500 Server Error` or DB operational failures.
- Emotion journals and compliance-related GDPR exports/deletions fail with write lock errors.
- System logs report `OperationalError: connection limit exceeded` or connection timeouts.

## 2. Detection
- **Alert Triggered**: `PostgresDatabaseDown` is actively firing.
- **Grafana Panel**: Check the **PostgreSQL Operational Errors** panel in the **Backend Overview** dashboard.
  - Spike in SQL transaction errors or connection pool depletion.
- **Log Correlation**:
  ```bash
  kubectl logs -n psychochat statefulset/psychochat-postgres --tail=100
  ```

## 3. Rollback & Failover
If the primary database is locking up or corrupted:
1. **Re-scale Pool/Restart StatefulSet Pods**:
   ```bash
   kubectl rollout restart statefulset/psychochat-postgres -n psychochat
   ```
2. **Execute Database Failover**:
   - If utilizing a High-Availability cluster (e.g. Patroni or Stolon), check the cluster sync state:
     ```bash
     kubectl exec -it -n psychochat psychochat-postgres-0 -- patronictl list
     ```
   - Trigger a failover if the primary node has drifted or failed.
3. **Emergency Backup Restore**:
   - Refer to the **Backup & Recovery Runbook** (`backup-recovery.md`) to pull the latest autonomous dump if database block corruptions are found.

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Lead Database Administrator (DBA)**: `dba-oncall@psikochat.com` (SLA response time: 5 minutes)
- **Escalation Tree**:
  1. Lead SRE / DBA (Notify within 10 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 20 minutes).
  3. VP of Engineering (Notify within 30 minutes if write block remains active).

## 5. Validation
1. **Database Ready Probe**:
   ```bash
   kubectl exec -it -n psychochat statefulset/psychochat-postgres -- pg_isready -h localhost
   ```
   *Expected Response*: `localhost:5432 - accepting connections`.
2. **App Connection Check**:
   ```bash
   curl -i -X GET https://api.psikochat.com/health
   ```
   *Expected Response*: `{"status": "ok", "database": true}`.

## 6. Postmortem
- **Timeline**: When did database connection latency spike? When did replication/sync recover?
- **Root Cause Analysis (RCA)**: Was it connection pool exhaustion, table locking due to unindexed queries, vacuum failures, or volume disk fulling?
- **Action Items**: Establish rigorous connection pooling limits (using PgBouncer if necessary) and index large emotion journal transaction tables.
