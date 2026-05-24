# Psychochat-AI — Kubernetes Infrastructure

> **Faz 10 Prompt 6 — Cloud-Native Kubernetes Architecture**
> Production-ready, autoscalable, TLS/WebSocket-capable, Secret-safe K8s deployment

---

## 📁 Manifest Directory Structure

| File | Kind | Purpose |
|------|------|---------|
| [`namespace.yaml`](namespace.yaml) | `Namespace` | Isolated `psychochat` namespace with correct labels |
| [`configmap.yaml`](configmap.yaml) | `ConfigMap` | All non-sensitive env vars (rate limits, flags, ports) |
| [`secrets.example.yaml`](secrets.example.yaml) | `Secret` | Placeholder template — **never commit real secrets** |
| [`backend-deployment.yaml`](backend-deployment.yaml) | `Deployment` | FastAPI app, 2–6 replicas, rolling update, probes |
| [`backend-service.yaml`](backend-service.yaml) | `Service` | ClusterIP, port 8001, internal routing |
| [`worker-deployment.yaml`](worker-deployment.yaml) | `Deployment` | Celery workers, graceful 120s shutdown |
| [`beat-deployment.yaml`](beat-deployment.yaml) | `Deployment` | Celery Beat scheduler, strictly 1 replica, Recreate |
| [`redis-deployment.yaml`](redis-deployment.yaml) | `Deployment + PVC` | Staging Redis with AOF persistence |
| [`redis-service.yaml`](redis-service.yaml) | `Service` | ClusterIP `redis:6379`, matches REDIS_URL hostname |
| [`postgres-statefulset.yaml`](postgres-statefulset.yaml) | `StatefulSet` | Staging PostgreSQL with permission initContainer |
| [`postgres-service.yaml`](postgres-service.yaml) | `Service` | ClusterIP `postgres:5432`, matches DATABASE_URL |
| [`pvc.yaml`](pvc.yaml) | `PersistentVolumeClaim` | data, uploads (5Gi), backups (5Gi) |
| [`ingress.yaml`](ingress.yaml) | `Ingress` | TLS, WebSocket, CORS, security headers, /metrics blocked |
| [`hpa.yaml`](hpa.yaml) | `HorizontalPodAutoscaler` | CPU 70% + Memory 80% → 2–6 backend pods |
| [`network-policy.yaml`](network-policy.yaml) | `NetworkPolicy` | 5-policy zero-trust network isolation |
| [`prometheus-scrape-config.yaml`](prometheus-scrape-config.yaml) | `PodMonitor + ConfigMap` | Dual scrape config (Operator + standalone) |

---

## 🏗️ Architecture Overview

```
Internet
    │
    ▼
[Nginx Ingress Controller]  ← TLS termination, CORS, WebSocket upgrade
api.psikochat.com:443
    │
    ▼  (NetworkPolicy: only ingress-nginx namespace allowed)
[psychochat-backend-svc]  (ClusterIP:8001)
    │
    ├──► [Pod: backend-0]  ┐
    ├──► [Pod: backend-1]  ├── HPA: 2–6 replicas, CPU 70% / Mem 80%
    └──► [Pod: backend-N]  ┘
         │         │
         ▼         ▼
    [postgres:5432]  [redis:6379]
    (StatefulSet)    (Deployment)
         ▲               ▲
         │               │
    [worker-0]       [worker-1]  ← Celery workers (2 replicas)
         │               │
         └───────────────┘
                 ▲
           [beat-0]  ← Scheduler (1 replica, Recreate strategy)

[Prometheus] ────── scrapes ──────► backend pods /metrics (Pod IPs, internal)
```

---

## 1️⃣ Namespace / ConfigMap / Secret Architecture

### Namespace
```bash
kubectl apply -f k8s/namespace.yaml
# Creates: namespace "psychochat"
# Labels: kubernetes.io/metadata.name=psychochat (required for NetworkPolicy cross-ns selectors)
```

### ConfigMap / Secret Separation

| Category | Location | Examples |
|----------|----------|---------|
| **Non-sensitive** | `configmap.yaml` | APP_ENV, LOG_LEVEL, CORS_ORIGINS, rate limits, POSTGRES_DB, REDIS_HOST |
| **Sensitive** | `secrets.yaml` (from example) | SECRET_KEY, DATABASE_URL, REDIS_URL, OPENAI_API_KEY, POSTGRES_PASSWORD |

All pods consume both via `envFrom: [configMapRef, secretRef]`.

---

## 2️⃣ Backend Deployment

- **Image**: `ghcr.io/deniznas/psychochat-ai:latest` (override with specific SHA in CI/CD)
- **Replicas**: min 2 → HPA scales to 6 at 70% CPU or 80% memory
- **Rolling Update**: `maxUnavailable: 0`, `maxSurge: 1` → zero downtime deploys
- **Topology Spread**: Pods distributed across nodes for HA
- **Probes**:
  - `startupProbe`: 12×5s = 60s max startup grace (handles model loading)
  - `readinessProbe`: `/health` every 10s — pod receives traffic only when ready
  - `livenessProbe`: `/health` every 15s — restarts hung pods
- **Security**: `runAsUser: 10001`, `allowPrivilegeEscalation: false`, `seccompProfile: RuntimeDefault`

---

## 3️⃣ Worker / Beat Deployment

### Celery Worker
- 2 replicas, `terminationGracePeriodSeconds: 120` (lets AI tasks finish)
- **Graceful shutdown**: `preStop` sends `celery control shutdown` → warm drain
- **Flags**: `--without-heartbeat --without-gossip --without-mingle` → reduces Redis chatter
- **Probes**: `celery inspect ping` for readiness/liveness

### Celery Beat
- **1 replica, Recreate strategy** → prevents duplicate scheduled task execution
- Lightweight (100m CPU, 128Mi RAM)
- Process-based liveness probe (`ps aux | grep celery.*beat`)
- Future HA option: **RedBeat** (Redis-backed distributed Beat scheduler)

---

## 4️⃣ PostgreSQL / Redis Strategy

| Environment | PostgreSQL | Redis |
|-------------|-----------|-------|
| **Local / Staging** | `postgres-statefulset.yaml` (StatefulSet + 5Gi PVC) | `redis-deployment.yaml` (Deployment + 1Gi PVC + AOF) |
| **Production** | ✅ AWS RDS or Google Cloud SQL | ✅ AWS ElastiCache or GCP Memorystore |

**Production migration steps:**
1. Delete StatefulSet and Redis Deployment
2. Update `REDIS_URL` and `DATABASE_URL` in `secrets.yaml` to managed endpoints
3. Add `?sslmode=require` to DATABASE_URL for managed PostgreSQL
4. Run `kubectl apply -f k8s/` — everything else works transparently

**StatefulSet improvements:**
- `initContainer` fixes PostgreSQL data directory permissions before DB starts
- `PGDATA=/var/lib/postgresql/data/pgdata` prevents mount root confusion
- `pg_isready` probes with correct user/db args

---

## 5️⃣ Ingress / TLS / WebSocket

### TLS
- **cert-manager** auto-provisions Let's Encrypt certificates
- Certificate stored in K8s Secret `psychochat-tls-cert`
- HSTS header: `max-age=31536000; includeSubDomains; preload`

### WebSocket
```yaml
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"   # 1 hour
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
nginx.ingress.kubernetes.io/configuration-snippet: |
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
```
Redis Pub/Sub handles cross-pod message routing → **sticky sessions NOT required**.

### Security Headers
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=31536000
```

### `/metrics` Protection
Not defined in any Ingress path → Nginx returns 404 for external requests.
Prometheus scrapes pod IPs directly (internal cluster network).

---

## 6️⃣ HPA / Autoscaling

```
Load Spike → CPU > 70% OR Memory > 80%
                    ↓
         [HPA: stabilizationWindowSeconds: 30]
                    ↓
         Scale UP: +2 pods per 60s event
         Max: 6 pods total

Calm Period (5 min sustained low load)
                    ↓
         Scale DOWN: -1 pod per 60s event
         Min: 2 pods always running
```

**Future**: KEDA (Kubernetes Event-Driven Autoscaling) for Celery queue-depth-based worker scaling.

---

## 7️⃣ NetworkPolicy / Security

5 NetworkPolicies enforce **zero-trust** network segmentation:

| Policy | Target | Allowed Ingress From | Allowed Egress To |
|--------|--------|-----------------------|-------------------|
| `postgres-isolation` | postgres pods | backend, worker, beat | DNS |
| `redis-isolation` | redis pods | backend, worker, beat | DNS |
| `backend-ingress-isolation` | backend pods | ingress-nginx ns, prometheus | postgres, redis, HTTPS:443, DNS |
| `worker-egress-policy` | worker pods | *(Egress only)* | postgres, redis, HTTPS:443, DNS |
| `beat-egress-policy` | beat pods | *(Egress only)* | redis, postgres, DNS |

**Container Security:**
- `runAsNonRoot: true`, `runAsUser: 10001`
- `allowPrivilegeEscalation: false`
- `capabilities.drop: [ALL]`
- `seccompProfile: RuntimeDefault`

---

## 8️⃣ Storage / Backup Strategy

| PVC | Size | Purpose | Production Replacement |
|-----|------|---------|----------------------|
| `psychochat-data-pvc` | 1Gi | App temp data, model cache | Keep or reduce |
| `psychochat-uploads-pvc` | 5Gi | User profile photos | **AWS S3 / GCS** |
| `psychochat-backups-pvc` | 5Gi | DB backup dumps | **AWS S3 / GCS** |
| `postgres-data-*` (StatefulSet) | 5Gi | PostgreSQL WAL + data | **RDS / Cloud SQL** |
| `psychochat-redis-pvc` | 1Gi | Redis AOF persistence | **ElastiCache / Memorystore** |

> ⚠️ `psychochat-uploads-pvc` uses `ReadWriteOnce` — works for single-node only.  
> Multi-node production: switch to S3 or `ReadWriteMany` (AWS EFS / GCP Filestore).

---

## 🚀 Deploy Commands

### Step 1 — Dry-Run Validation (no cluster needed)
```bash
kubectl apply --dry-run=client -f k8s/
```

### Step 2 — Prepare Secrets
```bash
# Copy example → real secrets file (gitignored)
cp k8s/secrets.example.yaml k8s/secrets.yaml

# Generate a real SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))" | base64

# Edit secrets.yaml with real base64-encoded values
# Then apply:
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
```

### Step 3 — Deploy Full Stack
```bash
kubectl apply -f k8s/
```

### Step 4 — Verify Pods & Services
```bash
kubectl get pods -n psychochat -w
kubectl get svc -n psychochat
kubectl get ingress -n psychochat
kubectl get hpa -n psychochat
kubectl get pvc -n psychochat
kubectl get networkpolicies -n psychochat
```

### Step 5 — Check Logs
```bash
# Backend
kubectl logs -n psychochat -l app=psychochat-backend --tail=50

# Worker
kubectl logs -n psychochat -l app=psychochat-worker --tail=50

# Beat
kubectl logs -n psychochat -l app=psychochat-beat --tail=50
```

### Step 6 — Health Check
```bash
kubectl exec -n psychochat deploy/psychochat-backend -- \
  curl -s http://localhost:8001/health | python -m json.tool
```

---

## 🧪 Local Minikube Test

```bash
# 1. Start cluster with ingress addon
minikube start --memory=4096 --cpus=2
minikube addons enable ingress
minikube addons enable metrics-server  # Required for HPA

# 2. Build and load local image (skip GHCR pull)
docker build -t psychochat-ai:local .
minikube image load psychochat-ai:local
# Then update image in backend/worker/beat deployments to psychochat-ai:local

# 3. Deploy
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml   # (copy from secrets.example.yaml first)
kubectl apply -f k8s/

# 4. Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=psychochat-backend -n psychochat --timeout=120s

# 5. Test health via NodePort tunnel
minikube service psychochat-backend-svc -n psychochat --url
# Or:
kubectl port-forward svc/psychochat-backend-svc 8001:8001 -n psychochat
curl http://localhost:8001/health

# 6. Test HPA (stress CPU to trigger scale)
kubectl run -n psychochat stress --image=busybox --restart=Never -- \
  sh -c "while true; do wget -q -O- http://psychochat-backend-svc:8001/health; done"
watch kubectl get hpa -n psychochat

# 7. Rolling update simulation
kubectl set image deployment/psychochat-backend \
  backend=ghcr.io/deniznas/psychochat-ai:v2 -n psychochat
kubectl rollout status deployment/psychochat-backend -n psychochat

# 8. Rollback if needed
kubectl rollout undo deployment/psychochat-backend -n psychochat
```

---

## 🔄 CI/CD Integration (GitHub Actions)

Add to `.github/workflows/deploy.yml`:

```yaml
- name: Deploy to Kubernetes
  run: |
    # Update image tag with commit SHA for reproducible deployments
    kubectl set image deployment/psychochat-backend \
      backend=ghcr.io/deniznas/psychochat-ai:${{ github.sha }} \
      -n psychochat

    kubectl set image deployment/psychochat-worker \
      worker=ghcr.io/deniznas/psychochat-ai:${{ github.sha }} \
      -n psychochat

    kubectl set image deployment/psychochat-beat \
      beat=ghcr.io/deniznas/psychochat-ai:${{ github.sha }} \
      -n psychochat

    # Wait for rollout to complete
    kubectl rollout status deployment/psychochat-backend -n psychochat --timeout=300s
```

---

## ⚠️ Production Checklist

- [ ] Replace `secrets.example.yaml` with real secrets via external secret manager
- [ ] Switch PostgreSQL StatefulSet → managed RDS/Cloud SQL
- [ ] Switch Redis Deployment → managed ElastiCache/Memorystore
- [ ] Switch uploads PVC → S3/GCS object storage
- [ ] Install cert-manager and create ClusterIssuer
- [ ] Install Nginx Ingress Controller (`ingress-nginx` namespace)
- [ ] Point DNS `api.psikochat.com` → Ingress load balancer IP
- [ ] Enable `metrics-server` for HPA to function
- [ ] Set specific image tags (not `:latest`) in all deployments
- [ ] Configure external Prometheus / Grafana dashboards
- [ ] Set up PodDisruptionBudget for backend (recommended: `minAvailable: 1`)
