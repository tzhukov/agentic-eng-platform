# Milestone 1: K8s Infrastructure Setup

## Overview
Goal: Provision a local Kubernetes environment for development using `kind`, `Tilt`, and `MetalLB`.

## Work Performed
- [x] Create `scripts/setup-cluster.sh` for Kind/MetalLB automation.
- [x] Configure `Tiltfile` for Helm-based orchestration.
- [x] Bootstrap Helm chart with pinned dependencies (Qdrant 1.18.1).
- [x] Set up K8s Secrets management (template provided in `scripts/setup-secrets.sh.template`).

## Proof of Completion
### Kind Cluster Info
```
Kubernetes control plane is running at https://127.0.0.1:45797
CoreDNS is running at https://127.0.0.1:45797/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy
```

### Nodes
```
NAME                            STATUS   ROLES           AGE   VERSION
agentic-project-control-plane   Ready    control-plane   68s   v1.35.0
agentic-project-worker          Ready    <none>          58s   v1.35.0
```

### MetalLB and System Pods
```
NAMESPACE            NAME                                                    READY   STATUS    RESTARTS   AGE
metallb-system       controller-79cccd6fdf-dj9dt                             1/1     Running   0          56s
metallb-system       speaker-b9pnk                                           1/1     Running   0          44s
metallb-system       speaker-j9jbj                                           1/1     Running   0          47s
```

### Tilt and Helm Readiness
- Helm chart initialized at `deploy/charts/agent`.
- Qdrant dependency downloaded (v1.18.1).
- `Tiltfile` created and ready for `tilt up`.
