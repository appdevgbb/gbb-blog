---
authors:
- diego_casati
- mohamad_al_jazaery
date: '2026-05-08'
description: >
  Deploy NVIDIA Dynamo on Azure Kubernetes Service with H100 GPU nodes using
  AKS Managed GPU and the Dynamo Kubernetes operator to run disaggregated LLM
  inference at scale. Then layer AI Runway on top for a visual dashboard that
  manages multiple inference runtimes — Dynamo, KAITO, and KubeRay — from a
  single UI.
tags:
- kubernetes
- aks
- gpu
- ai
- llm
- nvidia
- dynamo
- airunway
title: "NVIDIA Dynamo on AKS: Disaggregated LLM Inference with H100 GPUs"
---

# NVIDIA Dynamo on AKS: Disaggregated LLM Inference with H100 GPUs

You've got your AKS cluster, your GPU quota is approved, and you're ready to serve
large language models. But picking the right inference stack — vLLM, TensorRT-LLM,
SGLang, disaggregated vs. unified — can cost you days before your first token lands.

That's the gap [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo) fills.

<!-- truncate -->

Dynamo is an open-source inference serving framework that auto-profiles your
model and hardware, selects the optimal backend, and deploys a production-ready
inference graph as a Kubernetes-native custom resource. In this post we'll spin up an
AKS cluster with NVIDIA H100 nodes using AKS Managed GPU, install the Dynamo
platform, serve a first model, and then layer **AI Runway** on top to manage
Dynamo (and other runtimes like KAITO) through a visual dashboard — all from a
couple of shell scripts.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   AKS Cluster — dicasati-dynamo (southafricanorth)       │
│                                                                          │
│  ┌───────────────────────┐    ┌───────────────────────────────────────┐  │
│  │   System Node Pool    │    │        GPU Node Pool (h100pool)       │  │
│  │   (nodepool1)         │    │        Standard_ND96isr_H100_v5       │  │
│  │   Standard_D4ds_v5    │    │                                       │  │
│  │   1 × node            │    │  ┌─────────────────────────────────┐  │  │
│  │                       │    │  │   AKS Managed GPU               │  │  │
│  │  ┌─────────────────┐  │    │  │   - nvidia-driver (AKS)         │  │  │
│  │  │ dynamo-operator │  │    │  │   - nvidia-device-plugin (AKS)  │  │  │
│  │  │ etcd            │  │    │  │   - dcgm-exporter (AKS)         │  │  │
│  │  │ nats            │  │    │  │   - gpu-health-monitor (AKS)    │  │  │
│  │  └─────────────────┘  │    │  └─────────────────────────────────┘  │  │
│  └───────────────────────┘    │                                       │  │
│                               │  ┌─────────────────────────────────┐  │  │
│                               │  │  DynamoGraphDeployment (DGD)    │  │  │
│                               │  │  backend: auto                  │  │  │
│                               │  │  ┌──────────────────────────┐   │  │  │
│                               │  │  │ prefill worker (vLLM)    │   │  │  │
│                               │  │  │ decode  worker (vLLM)    │   │  │  │
│                               │  │  │ router / frontend        │   │  │  │
│                               │  │  └──────────────────────────┘   │  │  │
│                               │  └─────────────────────────────────┘  │  │
│                               └───────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
         │  inference API                      │  model weights
         ▼                                     ▼
  ┌─────────────┐                    ┌──────────────────┐
  │  curl /     │                    │  HuggingFace Hub  │
  │  OpenAI SDK │                    │  (or Azure Files  │
  └─────────────┘                    │   / Lustre cache) │
                                     └──────────────────┘
```

The GPU stack — driver, device plugin, DCGM metrics exporter, and GPU health
monitoring — is fully managed by AKS via `--enable-managed-gpu=true` on the node
pool. No GPU Operator installation is needed.

The Dynamo operator runs on the system node pool and manages
**DynamoGraphDeploymentRequests (DGDRs)**. A DGDR profiles the model against
available hardware, selects the best backend (vLLM, TensorRT-LLM, or SGLang),
and creates a **DynamoGraphDeployment (DGD)** that actually serves requests.
The DGD persists; the DGDR completes like a Kubernetes Job and can be cleaned up.

## Prerequisites

* Azure CLI (`az`) — [Install](https://learn.microsoft.com/cli/azure/install-azure-cli)
* `aks-preview` extension ≥ 19.0.0b29 — `az extension add --name aks-preview --allow-preview true`
* `ManagedGPUExperiencePreview` feature flag — [AKS Managed GPU docs](https://learn.microsoft.com/azure/aks/aks-managed-gpu-nodes)
* [Helm](https://helm.sh/docs/intro/install/) v3+
* [kubectl](https://kubernetes.io/docs/tasks/tools/) v1.24+
* Sufficient Azure quota for `Standard_ND96isr_H100_v5` VMs
* A [HuggingFace token](https://huggingface.co/settings/tokens) for gated or rate-limited model downloads

:::info Heads up
Check out the [Tools of the Trade: Working with Multiple
Clusters](../2025/11/27/tools-of-the-trade-working-with-multiple-clusters) blog post for how
to manage your working environment with `direnv`. I use that same approach here —
the environment variables live in `.envrc` and are loaded automatically when you
`cd` into the project directory.
:::

## Create the Environment

1. Clone this repository and enter the directory:

```bash
git clone https://github.com/appdevgbb/dynamo-on-aks.git
cd dynamo-on-aks
```

2. The `setup.sh` script writes a `.envrc` file with all the required variables:

```bash
cat .envrc
```

```bash
export CLUSTER_NAME="dicasati-dynamo"
export RESOURCE_GROUP="dicasati-dynamo"
export LOCATION="southafricanorth"
export KUBERNETES_VERSION="1.34.0"
export SYSTEM_NODE_SIZE="Standard_D4ds_v5"
export GPU_NODE_SIZE="Standard_ND96isr_H100_v5"
export KUBECONFIG="${PWD}/cluster.config"
```

3. Load the environment:

```bash
source .envrc
```

4. Create the Azure Resource Group:

```bash
az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}"
```

## Create the AKS Cluster

The cluster mirrors the `dicasati-dynamo` reference configuration:

| Node Pool   | VM SKU                         | Count       | OS Disk         | maxPods |
|-------------|--------------------------------|-------------|-----------------|---------|
| `agentpool` | `Standard_D4ds_v5`             | 4 (fixed)   | 150 GB Ephemeral | 250     |
| `h100pool`  | `Standard_ND96isr_H100_v5`     | 1–2 (auto)  | 1 TB Ephemeral   | 30      |

Run the setup script:

```bash
chmod +x setup.sh
./setup.sh
```

Or run the individual commands:

```bash
# System node pool
az aks create \
  --name                 "${CLUSTER_NAME}" \
  --resource-group       "${RESOURCE_GROUP}" \
  --location             "${LOCATION}" \
  --kubernetes-version   "${KUBERNETES_VERSION}" \
  --node-count           4 \
  --node-vm-size         "${SYSTEM_NODE_SIZE}" \
  --node-osdisk-size     150 \
  --node-osdisk-type     Ephemeral \
  --max-pods             250 \
  --network-plugin       azure \
  --network-plugin-mode  overlay \
  --pod-cidr             10.244.0.0/16 \
  --service-cidr         10.0.0.0/16 \
  --dns-service-ip       10.0.0.10 \
  --load-balancer-sku    standard \
  --generate-ssh-keys \
  --enable-defender \
  --enable-ai-toolchain-operator \
  --enable-oidc-issuer \
  --enable-workload-identity
```

Retrieve credentials:

```bash
az aks get-credentials \
  --name           "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --file           "${KUBECONFIG}"
```

Verify:

```bash
kubectl get nodes -o wide
```

### Add the H100 GPU Node Pool

:::info AKS Managed GPU
We use `--enable-managed-gpu=true` on the GPU node pool. AKS installs and manages
the full GPU stack: NVIDIA driver, device plugin, DCGM metrics exporter, and GPU
health monitoring. No GPU Operator installation is needed.

This feature requires the `aks-preview` extension (≥ 19.0.0b29) and the
`ManagedGPUExperiencePreview` feature flag. See
[AKS Managed GPU nodes](https://learn.microsoft.com/azure/aks/aks-managed-gpu-nodes)
for details.
:::

```bash
az aks nodepool add \
  --cluster-name         "${CLUSTER_NAME}" \
  --resource-group       "${RESOURCE_GROUP}" \
  --name                 h100pool \
  --node-vm-size         "${GPU_NODE_SIZE}" \
  --node-count           1 \
  --node-osdisk-size     1024 \
  --node-osdisk-type     Ephemeral \
  --max-pods             30 \
  --mode                 User \
  --kubernetes-version   "${KUBERNETES_VERSION}" \
  --node-taints          sku=gpu:NoSchedule \
  --enable-managed-gpu=true
```

Verify that GPUs are allocatable:

```bash
kubectl get nodes -l agentpool=h100pool \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
```

Expected output (8 GPUs for `Standard_ND96isr_H100_v5`):

```
aks-h100pool-xxxxx-vmss000000    8
```

## Install the Dynamo Platform

### HuggingFace Token Secret

Dynamo pulls model weights from HuggingFace Hub by default. A HuggingFace token
is **required** for gated models (e.g., Llama, Mistral) and recommended for all
models to avoid download rate limits. For open models like `Qwen/Qwen3-0.6B` the
token is optional but still good practice.

```bash
export HF_TOKEN=<your-huggingface-token>

kubectl create secret generic hf-token-secret \
  --from-literal=HF_TOKEN="${HF_TOKEN}"
```

### Install via Helm

```bash
export RELEASE_VERSION="1.0.2"
export NAMESPACE="dynamo-system"

helm fetch \
  "https://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-platform-${RELEASE_VERSION}.tgz"

helm install dynamo-platform "dynamo-platform-${RELEASE_VERSION}.tgz" \
  --namespace "${NAMESPACE}" \
  --create-namespace
```

:::tip Multinode and disaggregated inference
For deployments that span multiple GPU nodes (e.g., 70B+ models) uncomment the
Grove + KAI Scheduler flags:

```bash
helm install dynamo-platform "dynamo-platform-${RELEASE_VERSION}.tgz" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set "global.grove.install=true" \
  --set "global.kai-scheduler.install=true"
```

Grove is the default multinode orchestrator. Without it (or LWS), the Dynamo
operator returns a hard error on multinode deployments.
:::

Verify the platform pods are running:

```bash
kubectl get pods -n "${NAMESPACE}"
```

Expected output:

```
NAME                                                              READY   STATUS    AGE
dynamo-platform-dynamo-operator-controller-manager-xxxxxxxxxx    2/2     Running   2m50s
dynamo-platform-etcd-0                                           1/1     Running   2m50s
dynamo-platform-nats-0                                           2/2     Running   2m50s
dynamo-platform-nats-box-xxxxxxxxxx                              1/1     Running   2m51s
```

Verify CRDs:

```bash
kubectl get crd | grep dynamo
```

Expected CRDs:

```
dynamocomponentdeployments.nvidia.com
dynamographdeploymentrequests.nvidia.com
dynamographdeployments.nvidia.com
```

## GPU Node Pool Taints — The Gotcha You'll Hit

When you create the GPU node pool with `--node-taints sku=gpu:NoSchedule`, AKS
applies a taint that prevents any pod from scheduling on GPU nodes unless it
explicitly tolerates it. This is a good practice — it keeps system workloads off
your expensive GPU nodes.

However, **neither Dynamo nor AI Runway automatically inject tolerations for
custom taints**. They handle the standard NVIDIA taints
(`nvidia.com/gpu=present:NoSchedule`) but not user-defined ones like `sku=gpu`.
This means your model deployment will get stuck in `Pending` with an event like:

```
0/2 nodes are available: 1 Insufficient nvidia.com/gpu, 1 node(s) had
untolerated taint {sku: gpu}. preemption: 0/2 nodes are available:
2 Preemption is not helpful for scheduling.
```

### Option 1: Remove the taint (simpler)

If you don't need the taint (e.g., you only have GPU workloads on the GPU pool
anyway), remove it when creating the node pool by omitting `--node-taints`, or
update the existing pool:

```bash
az aks nodepool update \
  --cluster-name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --name h100pool \
  --node-taints ""
```

### Option 2: Patch the DGD after deployment (keeps the taint)

If you want to keep the taint to protect GPU nodes from non-GPU workloads, patch
the **DynamoGraphDeployment** to add tolerations after it's created:

```bash
DGD_NAME=$(kubectl get dgd -n "${NAMESPACE}" -o name | head -1 | cut -d/ -f2)

kubectl patch dgd "${DGD_NAME}" -n "${NAMESPACE}" --type=json -p='[
  {
    "op": "add",
    "path": "/spec/services/Frontend/extraPodSpec/tolerations",
    "value": [{"key":"sku","operator":"Equal","value":"gpu","effect":"NoSchedule"}]
  },
  {
    "op": "add",
    "path": "/spec/services/VllmWorker/extraPodSpec/tolerations",
    "value": [{"key":"sku","operator":"Equal","value":"gpu","effect":"NoSchedule"}]
  }
]'
```

:::warning Applies to all runtimes
This taint issue affects both **Dynamo** (DGDs) and **KAITO** (Workspaces)
deployments. The same toleration patch is needed for any inference provider
when custom node taints are in use. If you deploy through AI Runway, you'll
need to patch the underlying runtime resource after the deployment is created.
:::

## Deploy Your First Model

The **DynamoGraphDeploymentRequest (DGDR)** is the entrypoint for model
deployment. Submit one and Dynamo will:

1. Run an automated profiling job against your H100 nodes
2. Pick the optimal backend (`vLLM`, `TensorRT-LLM`, or `SGLang`)
3. Create a **DynamoGraphDeployment (DGD)** that serves the model

We'll start with `Qwen/Qwen3-0.6B` — small enough to deploy quickly but a good
end-to-end smoke test for the full pipeline.

```bash
kubectl apply -f manifests/quickstart.yaml -n "${NAMESPACE}"
```

The `quickstart.yaml` manifest:

```yaml
apiVersion: nvidia.com/v1beta1
kind: DynamoGraphDeploymentRequest
metadata:
  name: qwen3-quickstart
spec:
  model: Qwen/Qwen3-0.6B
  backend: auto
  image: "nvcr.io/nvidia/ai-dynamo/dynamo-planner:1.0.2"
```

Watch the DGDR lifecycle — it will transition through `Pending` → `Profiling` →
`Deploying` → `Deployed`:

```bash
kubectl get dgdr qwen3-quickstart -n "${NAMESPACE}" -w
```

:::note How long does profiling take?
On `Standard_ND96isr_H100_v5` nodes, profiling a 0.6B model typically takes
3–5 minutes. Larger models (7B, 13B) take proportionally longer. This is a
one-time cost; the resulting DGD can be reused.
:::

## Send a Request

Once the DGDR shows `Deployed`, find the frontend service and port-forward:

```bash
FRONTEND_SVC=$(kubectl get svc -n "${NAMESPACE}" -o name | grep frontend | head -1)
kubectl port-forward "${FRONTEND_SVC}" 8000:8000 -n "${NAMESPACE}" &
```

Send an OpenAI-compatible chat completion request:

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "What is NVIDIA Dynamo?"}],
    "max_tokens": 200
  }' | python3 -m json.tool
```

Example response:

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "NVIDIA Dynamo is an open-source inference serving framework..."
      }
    }
  ]
}
```

## AKS Storage Options for Model Caching

Large models (70B+) take hours to download per pod and will quickly exhaust
HuggingFace rate limits if every replica downloads independently. Use a shared
`ReadWriteMany` PVC to cache model weights across nodes.

| Storage Option              | Performance    | Best For                                   |
|-----------------------------|----------------|--------------------------------------------|
| Azure Managed Lustre        | Extremely high | Large multi-node models, shared cache      |
| Local CSI (ephemeral disk)  | Very high      | Fast model caching, warm restarts          |
| Azure Disk (Managed Disk)   | High           | Persistent single-writer model cache       |
| Azure Files                 | Medium         | Shared small/medium models                 |
| Azure Blob (CSI Fuse)       | Low–Medium     | Cold model storage, bootstrap downloads    |

The `manifests/cache.yaml` in this repository creates three PVCs following
the recommended tier strategy:

```bash
kubectl apply -f manifests/cache.yaml
```

```yaml
# Tier 1 — model weights (Azure Managed Lustre for high throughput)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-cache
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 100Gi
  storageClassName: "sc.azurelustre.csi.azure.com"
---
# Tier 2 — TensorRT compiled engines (Azure Files, persistent)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: compilation-cache
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 50Gi
  storageClassName: "azurefile-csi"
---
# Tier 3 — runtime tuning data (Azure Files, ephemeral OK)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: perf-cache
spec:
  accessModes: [ReadWriteMany]
  resources:
    requests:
      storage: 50Gi
  storageClassName: "azurefile-csi"
```

:::note Azure Managed Lustre prerequisite
`sc.azurelustre.csi.azure.com` is not installed by default. Verify available
storage classes first:

```bash
kubectl get storageclass
```

If the Lustre storage class is missing, use `azurefile-csi-premium` as a drop-in
replacement for the model cache with lower throughput.
:::

## Running on AKS Spot VMs

To reduce costs, Dynamo supports GPU node pools backed by [Azure Spot
VMs](https://azure.microsoft.com/products/virtual-machines/spot). AKS automatically
taints Spot nodes to prevent standard workloads from landing on them:

```
kubernetes.azure.com/scalesetpriority=spot:NoSchedule
```

Download the Dynamo AKS Spot values file and install with it:

```bash
curl -sO \
  https://raw.githubusercontent.com/ai-dynamo/dynamo/main/examples/deployments/AKS/values-aks-spot.yaml

helm install dynamo-platform "dynamo-platform-${RELEASE_VERSION}.tgz" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  -f values-aks-spot.yaml
```

The values file adds the required tolerations to the Dynamo operator, etcd, NATS,
and all core platform pods so they can be scheduled on Spot GPU nodes.

## AI Runway: A Dashboard for Dynamo (and More)

Once Dynamo is running, you can layer [AI Runway](https://github.com/kaito-project/airunway)
on top to get a visual dashboard for model deployment and management. AI Runway is
an open-source model deployment platform that supports multiple inference runtimes —
including Dynamo, KAITO (vLLM / llama.cpp), and KubeRay — through a unified UI and
Kubernetes-native CRDs.

### Why AI Runway?

| Without AI Runway | With AI Runway |
|-------------------|---------------|
| `kubectl apply -f dgdr.yaml` | Click **Deploy →** in the UI |
| Manual YAML for each model | Curated model catalog with sizing info |
| One runtime at a time | Multiple runtimes side by side (Dynamo + KAITO) |
| CLI-only monitoring | Visual deployment status and GPU utilization |

### Install the AI Runway Controller

AI Runway ships as a standalone binary with an embedded dashboard and a Kubernetes
controller that manages `ModelDeployment` custom resources. Download the latest
release for your platform:

```bash
# Example for macOS ARM64
curl -LO https://github.com/kaito-project/airunway/releases/download/v0.5.0/airunway-v0.5.0-darwin-arm64
chmod +x airunway-v0.5.0-darwin-arm64
```

Install the CRDs and controller into your cluster:

```bash
# From the AI Runway repository root
kubectl apply -f deploy/controller.yaml
```

Verify the controller is running:

```bash
kubectl get pods -n airunway-system
```

Expected output:

```
NAME                                          READY   STATUS    AGE
airunway-controller-manager-xxxxxxxxxx-xxxxx  1/1     Running   30s
```

### Register Dynamo as a Provider

AI Runway uses **InferenceProviderConfigs** to bridge its `ModelDeployment` CRs to
backend-specific resources. Deploy the Dynamo provider:

```bash
kubectl apply -f providers/dynamo/deploy/dynamo.yaml
```

Verify registration:

```bash
kubectl get inferenceproviderconfigs
```

```
NAME     READY   VERSION
dynamo   true    dynamo-provider:v0.1.0
```

### (Optional) Add KAITO as a Second Runtime

You can run multiple providers simultaneously. To add KAITO alongside Dynamo,
use the AKS AI toolchain operator add-on — this installs and manages the KAITO
workspace controller natively through AKS:

```bash
az aks update \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --enable-ai-toolchain-operator \
  --enable-oidc-issuer \
  --enable-workload-identity
```

:::tip Enable at cluster creation
If you're creating a fresh cluster, pass these flags to `az aks create` instead
of running a separate `az aks update`. The `setup.sh` script in this repository
already includes them:

```bash
az aks create \
  ... \
  --enable-ai-toolchain-operator \
  --enable-oidc-issuer \
  --enable-workload-identity
```
:::

Then deploy the AI Runway KAITO provider shim so AI Runway can talk to it:

```bash
kubectl apply -f providers/kaito/deploy/kaito.yaml
```

Both runtimes now appear in the dashboard:

```bash
kubectl get inferenceproviderconfigs
```

```
NAME     READY   VERSION
dynamo   true    dynamo-provider:v0.1.0
kaito    true    kaito-provider:v0.1.0
```

### Start the Dashboard

The AI Runway binary includes an embedded web dashboard. Start it pointing at
your cluster:

```bash
export KUBECONFIG="${PWD}/cluster.config"
airunway-v0.5.0-darwin-arm64 serve &
```

Then login to generate an auth token:

```bash
airunway-v0.5.0-darwin-arm64 login
```

Open the URL printed in the output (default: `http://<your-ip>:3001`). The
dashboard shows:

- **Model Catalog** — 18+ curated models with GPU sizing, context window, and
  supported engines (vLLM, SGLang, TensorRT-LLM, llama.cpp)
- **Deployments** — live status of all model deployments across providers
- **Settings** — cluster connection, GPU capacity, and provider health

From the catalog, click **Deploy →** on any model. AI Runway creates a
`ModelDeployment` CR, the registered provider translates it into the appropriate
backend resource (Dynamo DGD or KAITO Workspace), and the model is served on
your GPU nodes.

:::tip Accessing the dashboard remotely
The AI Runway server binds to all interfaces by default. If you're running it on
a remote machine, access it at `http://<machine-ip>:3001` instead of `localhost`.
:::

## Cleanup

Remove the sample deployment:

```bash
kubectl delete dgdr qwen3-quickstart -n "${NAMESPACE}"
```

Uninstall the Dynamo platform:

```bash
helm uninstall dynamo-platform -n "${NAMESPACE}"
kubectl get crd | grep "dynamo.*nvidia.com" | awk '{print $1}' | xargs kubectl delete crd
```

Delete the cluster and resource group:

```bash
az group delete --name "${RESOURCE_GROUP}" --yes --no-wait
```

## Conclusion

NVIDIA Dynamo on AKS removes the burden of choosing and tuning an LLM inference
backend. The auto-profiling step measures your actual hardware — H100 VRAM, NVLink
bandwidth, PCIe topology — and emits a deployment configuration that is optimised
for it. The Kubernetes-native DGDR/DGD model means you get GitOps-friendly
declarative deployments, Kubernetes-native scaling, and a clean OpenAI-compatible
API out of the box.

With AI Runway layered on top, you get a visual dashboard that unifies Dynamo,
KAITO, and KubeRay under a single interface. Deploy models with one click from
a curated catalog, monitor GPU utilization across providers, and switch inference
runtimes without rewriting YAML.

From here you can explore:

- **Disaggregated inference** — split prefill and decode across different nodes
  for lower TTFT at scale (requires Grove + KAI Scheduler and ideally RDMA)
- **Planner autoscaling** — Dynamo's Planner reads live TTFT/ITL metrics from
  Prometheus and adjusts replicas to meet an SLA
- **Model caching** — large models benefit enormously from a shared Azure Managed
  Lustre or Azure Files PVC to avoid per-pod downloads

## References

- [NVIDIA Dynamo — GitHub](https://github.com/ai-dynamo/dynamo)
- [AI Runway — GitHub](https://github.com/kaito-project/airunway)
- [KAITO — GitHub](https://github.com/kaito-project/kaito)
- [Dynamo on AKS — deployment guide](https://github.com/ai-dynamo/dynamo/blob/main/examples/deployments/AKS/AKS-deployment.md)
- [Dynamo Kubernetes installation guide](https://github.com/ai-dynamo/dynamo/blob/main/docs/kubernetes/installation-guide.md)
- [AKS Managed GPU nodes](https://learn.microsoft.com/azure/aks/aks-managed-gpu-nodes)
- [AKS — use NVIDIA GPUs](https://learn.microsoft.com/azure/aks/use-nvidia-gpu)
- [AKS CSI storage drivers](https://learn.microsoft.com/azure/aks/csi-storage-drivers)
- [Azure Managed Lustre CSI driver for AKS](https://learn.microsoft.com/azure/azure-managed-lustre/use-csi-driver-kubernetes)
- [Azure Spot VMs on AKS](https://learn.microsoft.com/azure/aks/spot-node-pool)
