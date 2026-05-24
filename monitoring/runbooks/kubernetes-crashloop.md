# Runbook: Kubernetes Pod CrashLoop & Storage Warnings

- **Severity Level**: SEV-2 (High)
- **Target Component**: `psychochat-platform` Kubernetes Cluster Infrastructure
- **Policy Constraint**: ZERO raw chat text, AI prompts, or crisis note extraction in logging/observability telemetry.

---

## 1. Symptom
- Pods display `CrashLoopBackOff`, `OOMKilled`, or `ImagePullBackOff` when running `kubectl get pods`.
- HPA cannot scale further under traffic peaks, resulting in request queuing or timeouts.
- File uploads or PostgreSQL transaction writes fail with `Disk Full` or `No space left on device` exceptions.

## 2. Detection
- **Alert Triggered**: `KubernetesPodCrashLoop` (SEV-2), `PersistentVolumeClaimFulling` (SEV-2), or `HPAAutoscalingLimitReached` (SEV-3) are active.
- **Grafana Panel**: Check the **Kubernetes Infrastructure** dashboard.
  - **Pod Restarts & Failures** panel displays high values.
  - **PVC Disk Burn** panel shows storage usage > 85%.
  - **HPA Pod Replica Scaling** panel hits the maximum replicas limit.
- **Log Correlation**:
  ```bash
  kubectl describe pod -n psychochat <pod-name>
  kubectl logs -n psychochat <pod-name> --previous
  ```

## 3. Rollback & Remediation
If an infrastructure change or a disk overrun occurred:
1. **Remediate CrashLoop (OOM or Probes)**:
   - If it was an Out-Of-Memory (OOM) crash, temporarily increase memory limits:
     ```bash
     kubectl set resources deployment/psychochat-backend -n psychochat --limits=memory=2Gi
     ```
   - If health probes are failing due to delayed startup: increase `initialDelaySeconds` in `k8s/backend-deployment.yaml` and redeploy.
2. **PVC Storage Expansion**:
   If a Persistent Volume Claim is fulling:
   - Edit the PVC size (if the storage class supports volume expansion):
     ```bash
     kubectl patch pvc <pvc-name> -n psychochat -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
     ```
3. **Autoscaling Cap Expansion**:
   If HPA hit its maximum replica cap during peak traffic:
   ```bash
   kubectl patch hpa psychochat-backend-hpa -n psychochat --patch '{"spec":{"maxReplicas":10}}'
   ```

## 4. Escalation
- **Primary On-Call SRE**: `sre-oncall@psikochat.com`
- **Cluster Administrator**: `k8s-admin@psikochat.com` (SLA response time: 15 minutes)
- **Escalation Tree**:
  1. Lead SRE Engineer (Notify within 20 minutes of alert trigger if unresolved).
  2. Principal Architect (Notify within 30 minutes).
  3. VP of Engineering (Notify within 60 minutes if cluster is in degraded state).

## 5. Validation
1. **Verify Pod Readiness**:
   ```bash
   kubectl get pods -n psychochat -l app.kubernetes.io/name=psychochat-backend
   ```
   *Expected Response*: All pods in `Running` state and `Ready (1/1)`.
2. **Verify Disk Allocation**:
   ```bash
   kubectl get pvc -n psychochat
   ```
   *Verify* that capacity has increased and status is `Bound`.

## 6. Postmortem
- **Timeline**: When did CrashLoops start? Was there an HPA scale trigger?
- **Root Cause Analysis (RCA)**: Was it memory leaks (OOM), strict probe startup delays, disk write leaks (e.g. unrotated logs/tmp files), or cluster node depletion?
- **Action Items**: Establish automatic log rotation inside pods, review standard container resource requests/limits, and adjust HPA step-scaling parameters.
