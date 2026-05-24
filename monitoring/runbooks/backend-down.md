# Runbook: Backend Down & High HTTP Error Rate

- **Severity Level**: SEV-1 (Critical)
- **Target Component**: `psychochat-backend` API Deployment
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Users encounter persistent connection timeouts, 502 Bad Gateway, or 504 Gateway Timeout errors.
- Both Android mobile clients and admin portals fail to login or authenticate.
- REST `/predict` and WebSockets `/ws/chat` are completely non-responsive.

## 2. Detection
- **Alert Triggered**: `BackendServiceDown` or `HTTPHighErrorRate` is firing.
- **Grafana Panel**: Check the **Psychochat-AI Backend Overview** dashboard.
  - **HTTP Request Rate** drops to absolute zero.
  - **HTTP Error Rate** spikes to > 15%.
- **Log Correlation**:
  - Run the following `kubectl` command to inspect pod logs:
    ```bash
    kubectl logs -n psychochat -l app.kubernetes.io/name=psychochat-backend --tail=100 --timestamps
    ```
  - Verify that `request_id` correlation is maintained and `user_id` values are hashed or masked.

## 3. Rollback
If the incident was triggered immediately after a new release (or CD pipeline trigger):
1. **Freeze Deployment**: Trigger an immediate deployment freeze under the **Error Budget Burn-Rate Freeze Policy** (burn-rate > 14.4x).
2. **Execute Kubernetes Rollback**:
   ```bash
   kubectl rollout undo deployment/psychochat-backend -n psychochat
   ```
3. **Verify Rollback Status**:
   ```bash
   kubectl rollout status deployment/psychochat-backend -n psychochat
   ```

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Incident Commander**: `incident-commander@psikochat.com` (SLA response time: 5 minutes)
- **Escalation Tree**:
  1. Lead SRE Engineer (Notify within 10 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 20 minutes).
  3. VP of Engineering (Notify within 30 minutes if rollback fails).

## 5. Validation
1. **Public Health Probe**:
   ```bash
   curl -i -X GET https://api.psikochat.com/health
   ```
   *Expected Response*: `HTTP 200 OK` with JSON `{"status": "ok", "database": true, "redis": true}`.
2. **Prometheus Scrape Validation**:
   ```bash
   curl -i -X GET http://<pod-ip>:8001/metrics
   ```
   *Note*: Ensure `/metrics` is NOT accessible publicly via ingress rules (returns 404 from public internet).

## 6. Postmortem
- **Timeline**: When did the outage start? When did rollback execute?
- **Root Cause Analysis (RCA)**: Was it a memory exhaustion (OOM), configuration drift, or faulty dependency?
- **Action Items**: Define concrete measures to prevent re-occurrence. File a tracking ticket with high priority.
