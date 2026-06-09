#!/bin/bash
set -e

CLUSTER_NAME="agentic-project"

# 1. Create Kind Cluster
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  echo "Creating kind cluster: ${CLUSTER_NAME}..."
  kind create cluster --name "${CLUSTER_NAME}" --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
- role: worker
networking:
  ipFamily: ipv4
EOF
else
  echo "Cluster ${CLUSTER_NAME} already exists."
fi

# 2. Install MetalLB
echo "Installing MetalLB..."
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.5/config/manifests/metallb-native.yaml

# Wait for MetalLB to be ready
echo "Waiting for MetalLB to be ready..."
kubectl wait --namespace metallb-system \
                --for=condition=ready pod \
                --selector=app=metallb \
                --timeout=120s

# 3. Configure MetalLB with Kind network range
echo "Configuring MetalLB with Kind network range..."

# Robust way to find the IPv4 subnet
KIND_NET_IP=$(docker network inspect kind -f '{{range .IPAM.Config}}{{.Subnet}}{{printf "\n"}}{{end}}' | grep -v ":" | cut -d'.' -f1,2 | head -n 1)
METALLB_RANGE="${KIND_NET_IP}.255.200-${KIND_NET_IP}.255.250"

kubectl apply -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: example
  namespace: metallb-system
spec:
  addresses:
  - ${METALLB_RANGE}
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: empty
  namespace: metallb-system
EOF

echo "Cluster ${CLUSTER_NAME} setup complete with MetalLB range: ${METALLB_RANGE}"
