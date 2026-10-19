# Operations Runbook — Day-1 & Day-2 Guide

## 1. Access & Credentials

### Kubernetes Cluster & Namespaces
All agent platform components run in the `agent-system` namespace.
```bash
# Verify current namespace context
kubectl get pods -n agent-system
```

### Local Dev Port-Forwards
When running outside the cluster or debugging locally:
| Service | Local Port | Target Port | Command |
|---|---|---|---|
| Agent API | 8000 | 8000 | `kubectl port-forward svc/agent-stack-api 8000:8000 -n agent-system` |
| Prometheus | 9090 | 9090 | `kubectl port-forward svc/prometheus-server 9090:80 -n agent-system` |
| Grafana | 3001 | 80 | `kubectl port-forward svc/grafana 3001:80 -n agent-system` |
| Alertmanager | 9093 | 9093 | `kubectl port-forward svc/alertmanager 9093:9093 -n agent-system` |
| Qdrant | 6333 | 6333 | `kubectl port-forward svc/agent-stack-qdrant 6333:6333 -n agent-system` |

---

## 2. Routine Operations

| Task | Cadence | Procedure |
|---|---|---|
| **Health & Invariant Check** | Daily / CI | Run `make handoff-check` |
| **Inspect SLO Error Budget** | Weekly | Inspect Prometheus recording rules: `job:http_requests_error_ratio:rate1h` |
| **Review Cost & Retry Ratio** | Weekly | Check Grafana `Retry Cost Ratio (%)` and `Projected Monthly Cost ($)` panels |
| **Rotate Provider API Keys** | Quarterly | Update K8s secrets (`agent-secrets`) and trigger rolling deployment restart |
| **Image Upgrade** | As released | Update image tag in values file and execute `helm upgrade` |

---

## 3. Configuration Management

**Rule:** Never use `kubectl edit` directly on production workloads. All changes must be recorded in Git and applied via Helm.

### Applying Configuration Changes:
```bash
# 1. Edit the relevant values file
vim deploy/charts/agent/values.yaml

# 2. Commit configuration changes
git commit -m "chore(config): adjust resource limits"

# 3. Apply via Helm
helm upgrade agent-stack ./deploy/charts/agent -f deploy/charts/agent/values.yaml -n agent-system
```

---

## 4. Key Management & Secrets

Secrets are mounted from Kubernetes secret `agent-secrets`:
```bash
kubectl get secret agent-secrets -n agent-system -o yaml
```

Required keys:
- `GROQ_API_KEY`: Groq inference provider key
- `GOOGLE_API_KEY`: Google Gemini provider key
- `E2B_API_KEY`: E2B Sandbox runtime key
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`: Tracing backend credentials
