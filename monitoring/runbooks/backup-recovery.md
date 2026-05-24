# Runbook: Automated Backup & Disaster Recovery

- **Severity Level**: SEV-2 (High)
- **Target Component**: `psychochat-platform` Autonomic Backups & Recovery System
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Automated cron backup scripts fail to execute, leaving zero daily archives in the secure object storage.
- An alert is raised indicating a database checksum variance or database corruption requires an emergency restore.
- Backup success gauges are flatlined, or last backup timestamp exceeds 26 hours.

## 2. Detection
- **Alert Triggered**: `AutonomicBackupFailure` is actively firing.
- **Grafana Panel**: Check the **Cache & Database Telemetry** panel or scrape custom metrics.
  - `psychochat_backup_failure_count` is > 0.
  - `psychochat_last_backup_timestamp` has drifted.
- **Log Correlation**:
  - Run the following command to check cronjob pod execution logs:
    ```bash
    kubectl logs -n psychochat jobs/psychochat-backup-cronjob
    ```

## 3. Rollback & Disaster Recovery (Restore)
If a critical database corruption has occurred and a full disaster recovery is required:
1. **Freeze Active Shipments**: Trigger an immediate deployment freeze under the **Error Budget Burn-Rate Freeze Policy** (burn-rate > 14.4x).
2. **Retrieve the Latest Backup**:
   Identify the latest verified `.sql.gz` dump from the secure, encrypted object storage container (e.g. S3, MinIO):
   ```bash
   aws s3 ls s3://psychochat-backups/postgres/
   ```
3. **Execute Database Restore**:
   - Suspend traffic to the backend pods (scale replicas to 0 to prevent write conflicts during dump import):
     ```bash
     kubectl scale deployment/psychochat-backend -n psychochat --replicas=0
     ```
   - Copy the verified dump archive into the primary database pod:
     ```bash
     kubectl cp latest_backup.sql.gz psychochat-postgres-0:/tmp/ -n psychochat
     ```
   - Execute the pg_restore command inside the container (totally privacy-safe, verifying masked tables are intact):
     ```bash
     kubectl exec -it -n psychochat psychochat-postgres-0 -- bash -c "gunzip -c /tmp/latest_backup.sql.gz | psql -U postgres -d psychochat"
     ```
4. **Restore Backend Replicas**:
   Re-scale backend pods once import succeeds:
   ```bash
   kubectl scale deployment/psychochat-backend -n psychochat --replicas=2
   ```

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Security & Compliance Lead**: `compliance@psikochat.com` (SLA response time: 10 minutes)
- **Lead Database Administrator (DBA)**: `dba-oncall@psikochat.com`
- **Escalation Tree**:
  1. Lead SRE / DBA (Notify within 10 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 20 minutes).
  3. VP of Engineering (Notify within 30 minutes if restore/dump is corrupted).

## 5. Validation
1. **Verify Database Integrity**:
   Verify that tables are restored and primary keys match, ensuring user credentials and compliance audit records are completely intact:
   ```bash
   kubectl exec -it -n psychochat psychochat-postgres-0 -- psql -U postgres -d psychochat -c "SELECT COUNT(*) FROM users;"
   ```
2. **Execute Public Health Probe**:
   ```bash
   curl -i -X GET https://api.psikochat.com/health
   ```
   *Expected Response*: `{"status": "ok", "database": true}`.

## 6. Postmortem
- **Timeline**: When did corruption/outage occur? When did dump import begin? When did pods return online?
- **Root Cause Analysis (RCA)**: Was it file system corruptions, AWS/S3 credential expirations, network policies blocking cronJob outgoing traffic, or Celery worker backup lock issues?
- **Action Items**: Automate dry-run recovery restores in staging clusters weekly to guarantee backup viability.
