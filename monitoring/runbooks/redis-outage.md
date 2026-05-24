# Runbook: Redis Cache & Pub/Sub Outage

- **Severity Level**: SEV-1 (Critical) / SEV-2 (High)
- **Target Component**: `psychochat-redis` Cache and Real-Time Pub/Sub
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- WebSocket multi-instance synchronization is broken. Real-time messages are not distributed across backend pods.
- Analytical calculations on the Mental Wellness Dashboard degrade in speed as they bypass caching.
- Logs are filled with `RedisConnectionError` warnings, triggering automated fallbacks to in-memory/local engines.

## 2. Detection
- **Alert Triggered**: `RedisCacheDown` or `CacheEfficacyDegradation` is firing.
- **Grafana Panel**: Check the **CacheHit vs Miss Rate** panel on the **Backend Overview** dashboard.
  - Redis cache operations display a flatline or fallback errors.
- **Log Correlation**:
  ```bash
  kubectl logs -n psychochat -l app=psychochat-backend --grep="RedisConnectionError" --tail=50
  ```

## 3. Rollback & Recovery
If Redis is locked or unresponsive:
1. **Restart Redis Deployment**:
   ```bash
   kubectl rollout restart deployment/psychochat-redis -n psychochat
   ```
2. **Examine Redis Persistence Volumes (PVC)**:
   Verify if the Redis volume is out of disk space:
   ```bash
   kubectl get pvc -n psychochat
   ```
3. **If Redis is in Cluster mode**: Verify master-replica sync state using CLI tools inside the pod.

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Cache Infrastructure Engineer**: `redis-admin@psikochat.com` (SLA response time: 10 minutes)
- **Escalation Tree**:
  1. Lead Infrastructure Engineer (Notify within 15 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 25 minutes).
  3. VP of Engineering (Notify within 45 minutes if state sync remains broken).

## 5. Validation
1. **Verify Backend Connection via API**:
   ```bash
   curl -i -X GET https://api.psikochat.com/health
   ```
   *Expected Response*: `{"status": "ok", "redis": true}`.
2. **Execute Internal Redis Ping Check**:
   ```bash
   kubectl exec -it -n psychochat deploy/psychochat-backend -- python -c "from src.core.redis_client import redis_client; print('Redis Status:', redis_client.ping())"
   ```
   *Expected Output*: `Redis Status: True`.

## 6. Postmortem
- **Timeline**: When did Redis socket timeouts start? When did recovery complete?
- **Root Cause Analysis (RCA)**: Was it a memory leaks/eviction configuration error (e.g. `maxmemory-policy`), replica synchronization failure, or resource depletion?
- **Action Items**: Establish better resource limits and backup schedules for the cluster cache state.
