# Runbook: WebSocket Gateway Outage

- **Severity Level**: SEV-2 (High)
- **Target Component**: `psychochat-backend` WebSocket Gateway
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Users experience persistent real-time chat disconnects, followed by endless reconnect loops on mobile apps.
- Heartbeats are timing out, forcing the server to close active sockets with code `4004`.
- Large events are rejected or rate-limited continuously under extreme load.

## 2. Detection
- **Alert Triggered**: `WebSocketGatewayOutage` is actively firing.
- **Grafana Panel**: Check the **WebSocket Gateway** dashboard.
  - Spike in **Heartbeat Timeout Rate** or **Disconnections by Reason** (e.g. `broken_pipe`, `heartbeat_timeout`).
  - Active connections count drops rapidly.
- **Log Correlation**:
  ```bash
  kubectl logs -n psychochat -l app.kubernetes.io/name=psychochat-backend --grep="WS:" --tail=100
  ```

## 3. Rollback & Remediation
If an ingress or deployment change caused socket leakage:
1. **Increase Backend Scale (HPA scale out)**:
   Ensure HPA has scaled the pods or manually override replica scale to handle active socket footprints:
   ```bash
   kubectl scale deployment/psychochat-backend -n psychochat --replicas=5
   ```
2. **Nginx Ingress Timeout Verification**:
   Verify that `k8s/ingress.yaml` has not modified the proxy timeouts (`nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"`). Redeploy ingress if modified:
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```
3. **Graceful Restart**:
   Perform a rolling update to purge dead/leaked sockets in memory:
   ```bash
   kubectl rollout restart deployment/psychochat-backend -n psychochat
   ```

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Network / WebSocket Specialist**: `net-engineer@psikochat.com` (SLA response time: 15 minutes)
- **Escalation Tree**:
  1. Lead SRE Engineer (Notify within 20 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 30 minutes).
  3. VP of Engineering (Notify within 60 minutes if real-time engine remains broken).

## 5. Validation
1. **Fetch WebSocket Gateway Status**:
   ```bash
   curl -i -X GET https://api.psikochat.com/ws/status -H "Authorization: Bearer <test-token>"
   ```
   *Expected Response*: `{"total_connections": <count>, "redis_pubsub_available": true}`.
2. **Validate Heartbeat Connection**:
   Connect via a command-line websocket client (e.g. `wscat`):
   ```bash
   wscat -c "wss://api.psikochat.com/ws/chat?token=<test-token>"
   ```
   Send `{"type": "ping"}`. Verify server returns `{"type": "pong"}` within 1 second.

## 6. Postmortem
- **Timeline**: When did heartbeat timeouts spike? Did scale-out resolve the bottleneck?
- **Root Cause Analysis (RCA)**: Was it file descriptor leaks, memory leaks in the connection registry (`self._connections`), Nginx Ingress connection drops, or client-side keep-alive failures?
- **Action Items**: Establish rigorous connection pooling limits and optimize the ping-pong heartbeat frequency on mobile clients.
