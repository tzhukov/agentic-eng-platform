# Design: Multi-Cloud Deployment — Agentic Stack

**Status:** Proposed  
**Author:** Forward Deployed Infrastructure  
**Last Updated:** 2026-06-27  

---

## 1. Overview

The `agentic` stack currently deploys exclusively to a local `kind` cluster via Tilt. This design defines how the **same Helm chart** is promoted to a real cloud-managed Kubernetes environment (GKE or EKS) with environment-specific overlays, preserving all observability, SLO instrumentation, and secret management built in earlier phases.

This is the primary gap between the current local lab and a credible client-facing deployment story. A Forward Deployed Infrastructure Engineer must be able to take the same artifact and land it in an environment they do not own.

---

## 2. Goals

- Deploy the full `agent-stack` (API + Qdrant + Prometheus + Grafana + Alertmanager) to GKE Autopilot or EKS using the existing Helm chart without modifying chart templates.
- Parameterize all environment-specific concerns (image registry, secrets backend, storage class, ingress, TLS) via `values-<env>.yaml` overlays.
- Document the delta between local and cloud so it reads as a client runbook.
- Prove the SLO instrumentation survives promotion — Prometheus still scrapes, Grafana dashboard still renders.

## 3. Non-Goals

- Multi-region active-active deployment.
- GitOps automation (ArgoCD/Flux) — deferred to a future phase.
- Cost optimization of cloud resources (this is a portfolio/demo deployment).

---

## 4. Architecture

### 4.1 Deployment Targets

| Environment | Provider | Cluster Type | Rationale |
|---|---|---|---|
| `local` | kind | Single-node | Fast iteration, no cost |
| `gke` | GCP | GKE Autopilot | Managed nodes, Workload Identity, Artifact Registry |
| `eks` | AWS | EKS Managed | ALB Ingress Controller, ECR, IAM IRSA |

Initial implementation targets **GKE Autopilot** as the primary cloud target. EKS is defined in the values overlay spec but deferred to a future milestone.

### 4.2 Helm Values Overlay Strategy

The chart remains unchanged. Environment behavior is driven entirely through values files:

```
deploy/charts/agent/
  values.yaml              ← defaults (local kind)
  values-gke.yaml          ← GKE Autopilot overlay
  values-eks.yaml          ← EKS overlay (future)
```

Helm invocation for cloud:

```bash
helm upgrade --install agent-stack ./deploy/charts/agent \
  -f deploy/charts/agent/values.yaml \
  -f deploy/charts/agent/values-gke.yaml \
  --namespace agent-system \
  --create-namespace
```

### 4.3 What Changes Between Environments

| Concern | Local (kind) | GKE Autopilot |
|---|---|---|
| Image registry | `docker.io` / local image load | `us-docker.pkg.dev/<project>/agentic` |
| Image pull | `imagePullPolicy: Never` | `imagePullPolicy: Always` |
| Secret management | `.env` file + K8s Secret manifest | External Secrets Operator → GCP Secret Manager |
| Storage class | `standard` (kind) | `standard-rwo` (GKE persistent SSD) |
| Ingress | `kubectl port-forward` | GKE Gateway API / GCE L7 Load Balancer |
| TLS | None | Google-managed certificate via `ManagedCertificate` or cert-manager |
| Qdrant persistence | `emptyDir` | `PersistentVolumeClaim` via `standard-rwo` |
| Prometheus scraping | Pod annotation discovery | Same (unchanged) |
| Node scheduling | Unrestricted | Autopilot auto-provisions, resource requests required |

---

## 5. Implementation Plan

### Phase 1: GKE Cluster Provisioning

**Script:** `scripts/provision-gke.sh`

```bash
gcloud container clusters create-auto agentic-demo \
  --region us-central1 \
  --project "${GCP_PROJECT}" \
  --release-channel regular
```

Outputs:
- Cluster kubeconfig written to `~/.kube/config` context `gke_<project>_us-central1_agentic-demo`

### Phase 2: Image Build & Push to Artifact Registry

**Script:** `scripts/push-image.sh`

```bash
IMAGE="us-docker.pkg.dev/${GCP_PROJECT}/agentic/agent-api:${GIT_SHA}"
docker build -t "${IMAGE}" ./
docker push "${IMAGE}"
```

The `values-gke.yaml` pins this image reference:

```yaml
image:
  repository: us-docker.pkg.dev/<project>/agentic/agent-api
  tag: "<GIT_SHA>"
  pullPolicy: Always
```

### Phase 3: Secret Management via External Secrets Operator

Instead of committing secrets or using `.env` files, integrate the [External Secrets Operator](https://external-secrets.io) against GCP Secret Manager.

Secrets to migrate:

| Secret Name | Current Source | GCP Secret Manager Key |
|---|---|---|
| `LITELLM_API_KEY` | `.env` | `agentic/litellm-api-key` |
| `E2B_API_KEY` | `.env` | `agentic/e2b-api-key` |
| `LANGFUSE_SECRET_KEY` | `.env` | `agentic/langfuse-secret-key` |
| `ALERTMANAGER_SMTP_PASSWORD` | Helm values | `agentic/smtp-password` |

`ExternalSecret` manifest (stored in `deploy/charts/agent/templates/external-secret.yaml`, gated by `values.externalSecrets.enabled`):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: agent-api-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: gcp-secret-store
    kind: ClusterSecretStore
  target:
    name: agent-api-secrets
    creationPolicy: Owner
  data:
    - secretKey: LITELLM_API_KEY
      remoteRef:
        key: agentic/litellm-api-key
```

Workload Identity binds the K8s service account to a GCP IAM service account with `roles/secretmanager.secretAccessor`.

### Phase 4: Ingress & TLS

Use GKE Gateway API for L7 load balancing:

```yaml
# deploy/charts/agent/templates/httproute.yaml (gated by values.gateway.enabled)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: agent-api
spec:
  parentRefs:
    - name: external-http
      namespace: kube-system
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: agent-stack-api
          port: 8000
```

TLS terminated at the load balancer via `ManagedCertificate`.

### Phase 5: Qdrant Persistent Storage

Update `values-gke.yaml` to enable Qdrant persistence:

```yaml
qdrant:
  persistence:
    enabled: true
    storageClass: standard-rwo
    size: 10Gi
```

### Phase 6: Deployment Smoke Test

**Script:** `scripts/smoke-test-cloud.sh`

```bash
BASE_URL="https://<ingress-ip>"
curl -f "${BASE_URL}/healthz"     || exit 1
curl -f "${BASE_URL}/readyz"      || exit 1
curl -f "${BASE_URL}/metrics"     || exit 1
curl -sf -XPOST "${BASE_URL}/query" \
  -H 'Content-Type: application/json' \
  -d '{"query": "ping"}' | jq .   || exit 1
echo "Smoke test passed."
```

---

## 6. `values-gke.yaml` — Full Overlay Spec

```yaml
# deploy/charts/agent/values-gke.yaml
# GKE Autopilot overlay — applied on top of values.yaml

image:
  repository: us-docker.pkg.dev/REPLACE_PROJECT/agentic/agent-api
  tag: REPLACE_GIT_SHA
  pullPolicy: Always

service:
  type: ClusterIP

gateway:
  enabled: true

externalSecrets:
  enabled: true
  gcpProject: REPLACE_PROJECT

qdrant:
  persistence:
    enabled: true
    storageClass: standard-rwo
    size: 10Gi

resources:
  requests:
    cpu: 250m
    memory: 256Mi
  limits:
    cpu: 1000m
    memory: 1Gi

# Autopilot requires explicit resource requests on all containers
observability:
  prometheus:
    resources:
      requests:
        cpu: 100m
        memory: 256Mi
  grafana:
    resources:
      requests:
        cpu: 50m
        memory: 128Mi
```

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| GKE Autopilot rejects pods with missing resource requests | Deployment fails | Audit all sub-charts; set explicit requests in overlay |
| External Secrets Operator not pre-installed | ESO `ExternalSecret` CRD missing | Add ESO as a Helm dependency (conditional) |
| Qdrant PVC provisioning delay | Qdrant pod stuck in `Pending` | Pre-provision PVC; readiness probe gates API startup |
| Image pull failure from Artifact Registry | `ErrImagePull` | Verify Workload Identity on node pool; check IAM binding |
| LLM provider latency higher from cloud egress | p95 latency SLO breach | Ensure LLM provider region matches cluster region |

---

## 8. Definition of Done

- [ ] `scripts/provision-gke.sh` provisions a healthy GKE Autopilot cluster.
- [ ] `scripts/push-image.sh` builds and pushes the agent image to Artifact Registry.
- [ ] `helm upgrade --install` with `values-gke.yaml` completes without error.
- [ ] All pods in `agent-system` namespace reach `Running` state within 5 minutes.
- [ ] `scripts/smoke-test-cloud.sh` passes all checks.
- [ ] Prometheus UI shows active scrape target for `agent-api` pod.
- [ ] Grafana `Agent Stack Dashboard` renders with live data.
- [ ] `docs/deployment/cloud-runbook.md` written and peer-reviewed.
