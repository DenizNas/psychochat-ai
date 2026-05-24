# Runbook: AI Orchestration & Provider Failure

- **Severity Level**: SEV-1 (Critical) / SEV-3 (Medium)
- **Target Component**: `psychochat-backend` Multi-Model AI Orchestrator
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Primary AI provider (OpenAI) fails, throwing API exceptions (rate limits, context window exceeded, auth errors).
- Requests fall back to the local/deterministic engine (`local_provider`) continuously, resulting in lower emotional depth scores.
- Daily budget budget cap exceeded warning is thrown, triggering forced local models.

## 2. Detection
- **Alert Triggered**: `AIProviderCriticalFailure` (SEV-1) or `AICostBudgetExceeded` (SEV-3) is actively firing.
- **Grafana Panel**: Check the **AI Orchestration** dashboard.
  - **AI Provider Error Rate** spikes for `openai`.
  - **Multi-Model Fallback Switches** increments.
  - **Cumulative Cost** panel reaches near the maximum daily budget.
- **Log Correlation**:
  ```bash
  kubectl logs -n psychochat -l app.kubernetes.io/name=psychochat-backend --grep="AI_ORCHESTRATOR" --tail=100
  ```

## 3. Rollback & Remediation
If an upstream API outage occurred or the budget cap was breached:
1. **Force Local Execution (Bypass OpenAI)**:
   If OpenAI is down globally, configure the orchestrator to bypass OpenAI immediately:
   ```bash
   kubectl set env deployment/psychochat-backend -n psychochat AI_PRIMARY_PROVIDER=local
   ```
2. **Upstream API Key Rotation**:
   If authentications are failing, update the API key secret:
   ```bash
   kubectl create secret generic psychochat-secrets -n psychochat --from-literal=OPENAI_API_KEY="new-key" --dry-run=client -o yaml | kubectl apply -f -
   kubectl rollout restart deployment/psychochat-backend -n psychochat
   ```
3. **Reset Daily Budget Limit (Emergency Override)**:
   If the daily limit was hit but overriding is business-approved:
   ```bash
   kubectl exec -it -n psychochat deploy/psychochat-redis -- redis-cli del ai_orchestrator:daily_cost:$(date -u +%Y-%m-%d)
   ```

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **AI / LLM Operations Specialist**: `ai-ops@psikochat.com` (SLA response time: 10 minutes)
- **Escalation Tree**:
  1. Lead AI Engineer (Notify within 10 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 20 minutes).
  3. VP of Engineering (Notify within 30 minutes if empathy engine is offline).

## 5. Validation
1. **Verify Backend Predictive Response**:
   ```bash
   curl -i -X POST https://api.psikochat.com/predict \
     -H "Authorization: Bearer <test-token>" \
     -H "Content-Type: application/json" \
     -d '{"text": "Bugün biraz yorgunum ama iyiyim."}'
   ```
   *Expected Response*: `HTTP 200 OK` with JSON fields `emotion`, `risk`, `response`. Contract response format MUST remain unchanged.
2. **Scrape Custom Telemetry**:
   ```bash
   curl -s http://<pod-ip>:8001/metrics | grep "psychochat_ai"
   ```
   *Verify* that fallback counters or error rates are not incrementing further for new requests.

## 6. Postmortem
- **Timeline**: When did OpenAI errors spike? When did circuit breaker trip? When did fallback activate?
- **Root Cause Analysis (RCA)**: Was it a service-wide OpenAI outage, API key expiry, rate-limit depletion, or a daily cost budget run-away?
- **Action Items**: Upgrade the local/deterministic fallback model to preserve high conversational quality when offline, and optimize token packing.
