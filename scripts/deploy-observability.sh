#!/bin/bash
# scripts/deploy-observability.sh
set -e

NAMESPACE="agent-system"

echo "=== Updating Agent Stack to Apply Metrics Annotations ==="
# Retrieve current running image tags to avoid ErrImagePull in kind cluster
API_IMAGE=$(kubectl get pods -n "${NAMESPACE}" -l app=agent-api -o jsonpath='{.items[?(@.status.phase=="Running")].spec.containers[0].image}')
API_TAG=$(echo $API_IMAGE | cut -d':' -f2)

WEB_IMAGE=$(kubectl get pods -n "${NAMESPACE}" -l app=agent-web -o jsonpath='{.items[?(@.status.phase=="Running")].spec.containers[0].image}')
WEB_TAG=$(echo $WEB_IMAGE | cut -d':' -f2)

# Retrieve current API keys from .env to restore them in the Kubernetes secret
GROQ_API_KEY=$(python3 -c 'import re; m = re.search(r"\[model\.groq\]\s*api_key\s*=\s*\"([^\"]+)\"", open(".env").read()); print(m.group(1) if m else "")')
GOOGLE_API_KEY=$(python3 -c 'import re; m = re.search(r"\[model\.google\]\s*api_key\s*=\s*\"([^\"]+)\"", open(".env").read()); print(m.group(1) if m else "")')
E2B_API_KEY=$(python3 -c 'import re; m = re.search(r"E2B_API_KEY\s*=\s*\"([^\"]+)\"", open(".env").read()); print(m.group(1) if m else "")')

echo "Applying template with API Tag: ${API_TAG}, Web Tag: ${WEB_TAG}"

helm template agent-stack ./deploy/charts/agent \
  --namespace "${NAMESPACE}" \
  --set qdrant.config.telemetry_disabled=true \
  --set agent.image.tag="${API_TAG}" \
  --set web.image.tag="${WEB_TAG}" \
  --set agent.groq_api_key="${GROQ_API_KEY}" \
  --set agent.google_api_key="${GOOGLE_API_KEY}" \
  --set agent.e2b_api_key="${E2B_API_KEY}" | kubectl apply -n "${NAMESPACE}" -f -

echo "=== Deploying Observability Stack (Phase 2) ==="

# 1. Update Helm repositories
echo "Updating Helm repositories..."
helm repo update

# 2. Deploy Prometheus (modular, alertmanager & other services disabled)
echo "Deploying Prometheus..."
helm upgrade --install prometheus prometheus-community/prometheus \
  --namespace "${NAMESPACE}" \
  -f deploy/observability/prometheus-values.yaml

# 3. Deploy Alertmanager (modular)
echo "Deploying Alertmanager..."
helm upgrade --install alertmanager prometheus-community/alertmanager \
  --namespace "${NAMESPACE}" \
  -f deploy/observability/alertmanager-values.yaml

# 4. Deploy Grafana (modular)
echo "Deploying Grafana..."
helm upgrade --install grafana grafana/grafana \
  --namespace "${NAMESPACE}" \
  -f deploy/observability/grafana-values.yaml

echo "Waiting for deployments to roll out..."
kubectl rollout status deployment/prometheus-server -n "${NAMESPACE}" --timeout=180s
kubectl rollout status statefulset/alertmanager -n "${NAMESPACE}" --timeout=180s
kubectl rollout status deployment/grafana -n "${NAMESPACE}" --timeout=180s

echo "=== Observability stack deployed successfully! ==="
