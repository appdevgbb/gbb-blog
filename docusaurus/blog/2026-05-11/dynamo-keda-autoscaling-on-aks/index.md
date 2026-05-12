---
authors:
  - diego_casati
  - mohamad_al_jazaery
date: '2026-05-11'
description: >
  Deploy NVIDIA Dynamo on AKS with disaggregated vLLM inference and KEDA
  autoscaling driven by TTFT p99 latency via Azure Managed Prometheus — no
  GPU Operator required.
tags:
  - kubernetes
  - aks
  - gpu
  - nvidia
  - dynamo
  - keda
  - autoscaling
  - llm
  - inference
title: "TTFT-Driven Autoscaling for Disaggregated LLM Inference with NVIDIA Dynamo on AKS"
---

# TTFT-Driven Autoscaling for Disaggregated LLM Inference with NVIDIA Dynamo on AKS

Most inference autoscalers react to CPU or GPU utilization. But for large language
models the metric that actually matters to users is **Time To First Token (TTFT)** —
how long they wait before the response starts streaming. A GPU can be 60% utilized
and still be delivering 30-second TTFT under a burst of long-context requests.

In this post I'll show how to wire [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo)
disaggregated inference together with [KEDA](https://keda.sh) on AKS so that the
system autoscales the decode worker fleet **directly on TTFT p99** — using Azure
Managed Prometheus as the metric source and AKS-managed GPU drivers so there is
no NVIDIA GPU Operator to maintain.

<!-- truncate -->

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AKS Cluster (eastus2)                               │
│                                                                             │
│  dynamo-cloud namespace                                                     │
│  ┌──────────────────────┐      ┌───────────────────────────────────────┐   │
│  │  Frontend  ×2        │─────▶│  VllmDecodeWorker  ×2 (min) → ×4 (max)│  │
│  │  (vllm-runtime)      │      │  (Standard_NC40ads_H100_v5)           │   │
│  │  port 8000           │      │  port 9090 (prometheus annotations)   │   │
│  └──────────────────────┘      └───────────────────────────────────────┘   │
│           │                                      │                          │
│           │ prometheus annotations               │                          │
│           ▼                                      ▼                          │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  Azure Monitor Agent (AMA) — pod-annotation scraping              │     │
│  │  config: podannotationnamespaceregex = "dynamo-cloud"             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  keda namespace                                                             │
│  ┌───────────────────────────────────────────────────────────────────┐      │
│  │  KEDA Operator  (azure.workload.identity/use: "true")            │      │
│  │  SA: keda-operator  ← annotated with UAMI client-id             │      │
│  │                                                                   │      │
│  │  ScaledObject: query TTFT p99 every 30s                         │      │
│  │    threshold: 300ms → scale DynamoGraphDeploymentScalingAdapter │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│  h100pool node pool (cluster-autoscaler: min=1 max=4)                      │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │
          ┌────────┴────────┐              ┌──────────────────────────────────┐
          │  Azure Managed  │◀─ remote ─── │  KEDA Operator                   │
          │  Prometheus     │   write       │  (OIDC token via Workload ID)    │
          │  (eastus2)      │              │  UAMI: keda-prometheus-reader    │
          └─────────────────┘              │  Role: Monitoring Data Reader    │
                                          └──────────────────────────────────┘
          ┌─────────────────┐
          │  Azure Managed  │
          │  Grafana        │
          │  (dynamo)       │
          │  dashboard:     │
          │  vLLM v2        │
          └─────────────────┘
```

When TTFT p99 exceeds 300 ms, KEDA increases the `replicas` field on the
`DynamoGraphDeploymentScalingAdapter`. The Dynamo operator brings up new decode
worker pods. If no GPU capacity is available the AKS cluster autoscaler adds
another `Standard_NC40ads_H100_v5` node (up to four).

## Prerequisites

* Azure CLI (`az`) with the `aks-preview` extension installed and updated
* `kubectl`, `helm` 3.x, `envsubst` (`brew install gettext` on macOS)
* An Azure subscription where you have **Owner** (to assign RBAC roles)
* An NVIDIA NGC account and API key — [ngc.nvidia.com/setup/api-key](https://ngc.nvidia.com/setup/api-key)
* `aiperf` for load testing — `pipx install aiperf`

:::info direnv
I use [direnv](https://direnv.net/) to auto-load `.envrc` when entering the
project directory. If you are not using it, `source .envrc` after every variable
change.
:::

## Create the Environment

1. Create a working directory:

```bash
mkdir -p ~/clusters/dynamo-aks && cd ~/clusters/dynamo-aks
```

2. Write the environment file:

```bash
cat <<'EOF'> .envrc
export CLUSTER_NAME="dynamo-cluster"       # change to your preferred name
export RESOURCE_GROUP="rg-dynamo"
export LOCATION="eastus2"
export KUBERNETES_VERSION="1.34.0"
export SYSTEM_NODE_SIZE="Standard_D4ds_v5"
export GPU_NODE_SIZE="Standard_NC40ads_H100_v5"
export KUBECONFIG="${PWD}/cluster.config"
# Filled in after the cluster is created (Step 4)
export PROMETHEUS_ENDPOINT=""
# Your NGC API key — required to pull Dynamo images from nvcr.io
export NGC_API_KEY=""
export GRAFANA_NAME="dynamo"
EOF
```

3. Load the environment:

```bash
source .envrc
```

4. Create the resource group:

```bash
az group create \
  --name "${RESOURCE_GROUP}" \
  --location "${LOCATION}"
```

## Create the AKS Cluster

Create the cluster with OIDC issuer and Workload Identity enabled. We skip the
GPU Operator entirely — AKS will manage the NVIDIA drivers natively via
`--enable-managed-gpu` on the GPU node pool.

1. Create the cluster with a single system node:

```bash
az aks create \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --location "${LOCATION}" \
  --kubernetes-version "${KUBERNETES_VERSION}" \
  --node-count 1 \
  --node-vm-size "${SYSTEM_NODE_SIZE}" \
  --enable-oidc-issuer \
  --enable-workload-identity \
  --network-plugin azure \
  --network-plugin-mode overlay \
  --generate-ssh-keys
```

2. Add the H100 GPU node pool with AKS-managed GPU drivers:

```bash
az aks nodepool add \
  --name h100pool \
  --cluster-name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --node-count 1 \
  --node-vm-size "${GPU_NODE_SIZE}" \
  --node-taints "sku=gpu:NoSchedule" \
  --enable-managed-gpu
```

:::note AKS Managed GPU vs GPU Operator
`--enable-managed-gpu` tells AKS to install and manage the NVIDIA device plugin,
driver, and DCGM exporter on GPU nodes automatically. You do **not** need the
NVIDIA GPU Operator. The `sku=gpu:NoSchedule` taint ensures only pods that
explicitly tolerate it land on GPU nodes.
:::

3. Retrieve credentials:

```bash
az aks get-credentials \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --file "${KUBECONFIG}"
```

4. Verify:

```bash
kubectl get nodes -o wide
```

Expected output:

```
NAME                               STATUS   ROLES    AGE   VERSION
aks-h100pool-25770640-vmss000000   Ready    <none>   5m    v1.34.0
aks-nodepool1-28586722-vmss000000  Ready    <none>   10m   v1.34.0
```

## Enable Azure Managed Prometheus

`--enable-azure-monitor-metrics` deploys the Azure Monitor Agent (AMA) into the
cluster and creates an Azure Monitor Workspace in the region's default resource
group. KEDA will query this workspace for TTFT metrics.

1. Enable the addon:

```bash
az aks update \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --enable-azure-monitor-metrics
```

The CLI prints the workspace resource ID as it runs:

```
Using Azure Monitor Workspace: .../DefaultAzureMonitorWorkspace-eastus2
```

2. Get the Prometheus query endpoint and update `.envrc`:

```bash
PROMETHEUS_ENDPOINT=$(az monitor account list \
  --query "[?location=='${LOCATION}'].metrics.prometheusQueryEndpoint | [0]" \
  -o tsv)

echo "export PROMETHEUS_ENDPOINT=\"${PROMETHEUS_ENDPOINT}\"" >> .envrc
source .envrc
echo "${PROMETHEUS_ENDPOINT}"
```

## Install the Dynamo Platform

Dynamo ships as a Helm chart on the NVIDIA NGC Helm registry. The chart installs
the Dynamo operator (which reconciles `DynamoGraphDeployment` CRDs) and a NATS
server used for inter-component messaging.

1. Add the Helm repository:

```bash
helm repo add nvidia-dynamo https://helm.ngc.nvidia.com/nvidia/ai-dynamo
helm repo update nvidia-dynamo
```

2. Create the namespace:

```bash
kubectl create namespace dynamo-system
```

3. Create the NGC image pull secret **before** installing the chart so the operator
can pull its init container from `nvcr.io`:

```bash
kubectl create secret docker-registry nvcr-imagepullsecret \
  --docker-server=nvcr.io \
  --docker-username='$oauthtoken' \
  --docker-password="${NGC_API_KEY}" \
  --namespace dynamo-system
```

:::tip Getting an NGC API key
Log in to [ngc.nvidia.com](https://ngc.nvidia.com), click your avatar →
**Setup** → **Generate API Key**. The key format is `<org>:<random-uuid>`.
:::

4. Install the Dynamo Platform:

```bash
helm upgrade --install dynamo-platform nvidia-dynamo/dynamo-platform \
  --version 1.0.2 \
  --namespace dynamo-system \
  --set prometheusEndpoint="${PROMETHEUS_ENDPOINT}"
```

The `prometheusEndpoint` setting tells the Dynamo Planner where to query metrics
for its internal scheduling decisions.

5. Wait for the operator and NATS to be ready:

```bash
kubectl wait pod \
  --for=condition=Ready \
  --selector=app.kubernetes.io/name=dynamo-operator \
  --namespace dynamo-system \
  --timeout=300s

kubectl get pods -n dynamo-system
```

Expected output:

```
NAME                                                              READY   STATUS
dynamo-platform-dynamo-operator-controller-manager-868fb99x4t56  1/1     Running
dynamo-platform-nats-0                                            2/2     Running
```

## Install KEDA with Azure Workload Identity

KEDA will scale the decode worker fleet by querying Azure Managed Prometheus for
TTFT p99. To authenticate to the Prometheus endpoint without secrets we use **AKS
Workload Identity**: a User-Assigned Managed Identity (UAMI) federates with the
`keda-operator` Kubernetes service account, and KEDA exchanges the resulting OIDC
token for an Azure AD access token on every metric query.

### Create the UAMI

```bash
az identity create \
  --name keda-prometheus-reader \
  --resource-group "${RESOURCE_GROUP}" \
  --location "${LOCATION}"

export KEDA_CLIENT_ID=$(az identity show \
  --name keda-prometheus-reader \
  --resource-group "${RESOURCE_GROUP}" \
  --query clientId -o tsv)

export KEDA_PRINCIPAL_ID=$(az identity show \
  --name keda-prometheus-reader \
  --resource-group "${RESOURCE_GROUP}" \
  --query principalId -o tsv)

echo "client-id:    ${KEDA_CLIENT_ID}"
echo "principal-id: ${KEDA_PRINCIPAL_ID}"
```

### Assign Monitoring Data Reader on the AMW

AKS places the Azure Monitor Workspace in a system-managed resource group
(`DefaultResourceGroup-<location>`), not in the cluster's resource group.
Look up the workspace ID by matching the endpoint URL:

```bash
export AMW_ID=$(az monitor account list \
  --query "[?metrics.prometheusQueryEndpoint=='${PROMETHEUS_ENDPOINT}'].id | [0]" \
  -o tsv)

echo "AMW ID: ${AMW_ID}"

az role assignment create \
  --assignee-object-id "${KEDA_PRINCIPAL_ID}" \
  --assignee-principal-type ServicePrincipal \
  --role "Monitoring Data Reader" \
  --scope "${AMW_ID}"
```

### Create the Federated Credential

```bash
export OIDC_ISSUER=$(az aks show \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query oidcIssuerProfile.issuerUrl -o tsv)

az identity federated-credential create \
  --name keda-fed-cred \
  --identity-name keda-prometheus-reader \
  --resource-group "${RESOURCE_GROUP}" \
  --issuer "${OIDC_ISSUER}" \
  --subject "system:serviceaccount:keda:keda-operator" \
  --audience api://AzureADTokenExchange
```

### Install KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update kedacore

helm upgrade --install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --version 2.16.0 \
  --set podIdentity.azureWorkload.enabled=true \
  --wait \
  --timeout 300s
```

The `podIdentity.azureWorkload.enabled=true` flag adds the
`azure.workload.identity/use: "true"` label to the KEDA operator pod, which
signals the AKS workload identity mutating webhook to inject an OIDC token volume.

### Annotate the Service Account

```bash
kubectl annotate serviceaccount keda-operator \
  --namespace keda \
  "azure.workload.identity/client-id=${KEDA_CLIENT_ID}" \
  --overwrite

kubectl rollout restart deployment/keda-operator -n keda
kubectl rollout status  deployment/keda-operator -n keda --timeout=120s
```

## Deploy the Autoscaling Stack

All application resources live in the `dynamo-cloud` namespace.

### Prepare the Namespace and Secrets

```bash
kubectl create namespace dynamo-cloud

# Copy the NGC pull secret into the app namespace
kubectl get secret nvcr-imagepullsecret -n dynamo-system -o json \
  | python3 -c "
import json, sys
obj = json.load(sys.stdin)
obj['metadata'] = {'name': obj['metadata']['name']}
print(json.dumps(obj))
" | kubectl apply -n dynamo-cloud -f -
```

### Enable AMA Pod-Annotation Scraping

By default, the Azure Monitor Agent only scrapes the cluster-level endpoints it
knows about. To have it pick up Dynamo's Prometheus annotations on pods in
`dynamo-cloud`, apply a custom ConfigMap:

```bash
cat <<'EOF' | kubectl apply -f -
kind: ConfigMap
apiVersion: v1
metadata:
  name: ama-metrics-settings-configmap
  namespace: kube-system
data:
  schema-version: v1
  config-version: ver1
  settings: |-
    [prometheus_data_collection_settings.cluster]
    interval = "1m"
    monitor_kubernetes_pods = true
    podannotationnamespaceregex = "dynamo-cloud"
EOF
```

### Deploy the DynamoGraphDeployment

`DynamoGraphDeployment` (DGD) is the primary Dynamo resource. It describes the
full inference graph — in this case a **Frontend** tier that handles the
OpenAI-compatible API and routes to a **VllmDecodeWorker** tier that holds the
GPU and runs vLLM.

```bash
cat <<'EOF' | kubectl apply -n dynamo-cloud -f -
apiVersion: nvidia.com/v1alpha1
kind: DynamoGraphDeployment
metadata:
  name: vllm-agg
spec:
  services:
    Frontend:
      replicas: 2
      image: nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.0.1
      imagePullSecrets:
        - name: nvcr-imagepullsecret
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    VllmDecodeWorker:
      replicas: 2
      image: nvcr.io/nvidia/ai-dynamo/vllm-runtime:1.0.1
      imagePullSecrets:
        - name: nvcr-imagepullsecret
      scalingAdapter:
        enabled: true
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
      resources:
        limits:
          nvidia.com/gpu: "1"
        requests:
          nvidia.com/gpu: "1"
      tolerations:
        - key: "sku"
          operator: "Equal"
          value: "gpu"
          effect: "NoSchedule"
      args:
        - python3
        - -m
        - dynamo.vllm
        - --model
        - Qwen/Qwen3-0.6B
EOF
```

Wait for the operator to create the child resources:

```bash
kubectl get dynamographdeployment -n dynamo-cloud -w
kubectl get dgdsa -n dynamo-cloud
```

`dgdsa` is short for `DynamoGraphDeploymentScalingAdapter` — the resource KEDA
will target. You should see one entry named `vllm-agg-vllmdecodeworker`.

### Deploy the KEDA ScaledObject

The `TriggerAuthentication` tells KEDA to use Azure Workload Identity. The
`ScaledObject` queries TTFT p99 every 30 seconds and adjusts the `replicas` field
on the `DynamoGraphDeploymentScalingAdapter` when latency crosses 300 ms.

:::warning Do NOT set `authModes: "bearer"`
When using `provider: azure-workload` in a `TriggerAuthentication`, the workload
identity provider handles token acquisition automatically. Adding
`authModes: "bearer"` to the Prometheus trigger causes KEDA to look for a static
bearer token in a Kubernetes secret — which doesn't exist — and the ScaledObject
will stay `READY=False` with the error:

```
bearer token is required when bearer auth is enabled
```

Leave `authModes` unset.
:::

```bash
cat <<EOF | kubectl apply -n dynamo-cloud -f -
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: azure-managed-prometheus-auth
spec:
  podIdentity:
    provider: azure-workload
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-agg-decode-scaler
spec:
  scaleTargetRef:
    apiVersion: nvidia.com/v1alpha1
    kind: DynamoGraphDeploymentScalingAdapter
    name: vllm-agg-vllmdecodeworker
  minReplicaCount: 2
  maxReplicaCount: 4
  pollingInterval: 30
  cooldownPeriod:  120
  triggers:
    - type: prometheus
      metadata:
        serverAddress: "${PROMETHEUS_ENDPOINT}"
        metricName: dynamo_ttft_p99
        query: |
          histogram_quantile(0.99,
            sum(rate(dynamo_frontend_time_to_first_token_seconds_bucket[2m]))
            by (le)
          )
        threshold: "0.3"
        activationThreshold: "0.3"
      authenticationRef:
        name: azure-managed-prometheus-auth
EOF
```

Verify the ScaledObject becomes ready (allow 15–30 seconds):

```bash
kubectl get scaledobject -n dynamo-cloud
kubectl get hpa -n dynamo-cloud
```

Expected output:

```
NAME                     SCALETARGETKIND                              SCALETARGETNAME              MIN   MAX   READY   ACTIVE
vllm-agg-decode-scaler   nvidia.com/v1alpha1.DynamoGraphDeploymentScalingAdapter   vllm-agg-vllmdecodeworker   2     4     True    False

NAME                              REFERENCE                                                    TARGETS        MINPODS   MAXPODS   REPLICAS
keda-hpa-vllm-agg-decode-scaler   DynamoGraphDeploymentScalingAdapter/vllm-agg-vllmdecodeworker   0/300m (avg)   2         4         2
```

`READY=True` and `ACTIVE=False` at idle is correct — the system is at minimum
replicas because TTFT is below threshold.

## Expose the Frontend

The `vllm-agg-frontend` service is created as `ClusterIP` by default. Patch it to
`LoadBalancer` so external clients (including `aiperf`) can reach it:

```bash
kubectl patch svc vllm-agg-frontend -n dynamo-cloud \
  -p '{"spec":{"type":"LoadBalancer","ports":[{"port":8000,"targetPort":8000}]}}'
```

Wait for the external IP:

```bash
kubectl get svc vllm-agg-frontend -n dynamo-cloud -w
```

Once `EXTERNAL-IP` is assigned, smoke test:

```bash
EXTERNAL_IP=$(kubectl get svc vllm-agg-frontend -n dynamo-cloud \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

curl -s "http://${EXTERNAL_IP}:8000/v1/models" | python3 -m json.tool
```

Expected:

```json
{
    "object": "list",
    "data": [
        {
            "id": "Qwen/Qwen3-0.6B",
            "object": "model",
            "created": 1778534284,
            "owned_by": "nvidia"
        }
    ]
}
```

## Connect Azure Managed Grafana

The `dynamo` Grafana instance is in `rg-dynamo`. We'll add the AMW as a data
source and import the vLLM monitoring dashboard.

1. Grant yourself Grafana Admin (owner of the subscription can do this):

```bash
MY_OID=$(az ad signed-in-user show --query id -o tsv)
GRAFANA_SCOPE=$(az grafana show \
  --name "${GRAFANA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query id -o tsv)

az role assignment create \
  --assignee-object-id "${MY_OID}" \
  --assignee-principal-type User \
  --role "Grafana Admin" \
  --scope "${GRAFANA_SCOPE}"
```

2. Add the Azure Managed Prometheus data source:

```bash
az grafana data-source create \
  --name "${GRAFANA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --definition "{
    \"name\": \"Azure Managed Prometheus - EastUS2\",
    \"type\": \"prometheus\",
    \"access\": \"proxy\",
    \"url\": \"${PROMETHEUS_ENDPOINT}\",
    \"jsonData\": {
      \"httpMethod\": \"POST\",
      \"azureCredentials\": {\"authType\": \"msi\"}
    },
    \"isDefault\": true
  }"
```

Note the `uid` from the response — you'll need it for the dashboard import.

3. Import the vLLM Monitoring dashboard (Grafana ID 24756) using an Azure AD
bearer token (Grafana's API key feature requires the service accounts feature to
be enabled first, so we use the AAD token directly):

```bash
GRAFANA_URL=$(az grafana show \
  --name "${GRAFANA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --query properties.endpoint -o tsv)

# Azure Managed Grafana resource ID for token scope
GRAFANA_TOKEN=$(az account get-access-token \
  --resource "ce34e7e5-485f-4d76-964f-b3d2b16d1e4f" \
  --query accessToken -o tsv)

DS_UID=$(az grafana data-source show \
  --name "${GRAFANA_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --data-source-name "Azure Managed Prometheus - EastUS2" \
  --query uid -o tsv)

# Download the dashboard JSON from grafana.com
curl -sf "https://grafana.com/api/dashboards/24756/revisions/latest/download" \
  -o /tmp/vllm-dashboard.json

# Strip the id field and import
PAYLOAD=$(python3 -c "
import json
dash = json.load(open('/tmp/vllm-dashboard.json'))
dash.pop('id', None)
print(json.dumps({
    'dashboard': dash,
    'overwrite': True,
    'folderId': 0,
    'inputs': [{'name': 'DS_PROMETHEUS', 'type': 'datasource',
                'pluginId': 'prometheus', 'value': '${DS_UID}'}]
}))
")

curl -sf -X POST "${GRAFANA_URL}/api/dashboards/import" \
  -H "Authorization: Bearer ${GRAFANA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" | python3 -m json.tool
```

4. Link the AKS cluster to Grafana so managed dashboards (node metrics, workload
views) are provisioned automatically:

```bash
az aks update \
  --name "${CLUSTER_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --enable-azure-monitor-metrics \
  --azure-monitor-workspace-resource-id "${AMW_ID}" \
  --grafana-resource-id "${GRAFANA_SCOPE}" \
  --no-wait
```

Open the dashboard:

```bash
echo "${GRAFANA_URL}/d/vllm-master-v2/vllm-monitoring-v2"
```

## Load Test and Watch Autoscaling

`aiperf` is a benchmarking tool built for LLM inference. Install it with `pipx`:

```bash
brew install pipx
pipx install aiperf
export PATH="$HOME/.local/bin:$PATH"
aiperf --version  # should print 0.7.0
```

:::note Python compatibility
If `aiperf` crashes with `AttributeError: 'ForwardRef' object has no attribute
'default_parameter'` at startup, you are running Python 3.14. Install with
Python 3.12 instead:

```bash
brew install python@3.12
pipx install aiperf --python /opt/homebrew/opt/python@3.12/bin/python3.12
```
:::

Run a 2,000-request load profile at 8 req/s with 3,000-token inputs. This rate
will push TTFT comfortably above the 300 ms threshold within the first polling
interval, without exhausting the TCP connection pool:

```bash
aiperf profile \
  --model Qwen/Qwen3-0.6B \
  --tokenizer Qwen/Qwen3-0.6B \
  --endpoint-type chat \
  --url "${EXTERNAL_IP}:8000" \
  --streaming \
  --synthetic-input-tokens-mean 3000 \
  --output-tokens-mean 250 \
  --request-rate 8.0 \
  --request-count 2000 \
  --num-dataset-entries 6000 \
  --artifact-dir /tmp/scaling_test
```

:::warning Choose your request rate carefully
A rate of 42 req/s with 3,000-token inputs overwhelms a 2-worker Qwen3-0.6B
deployment — the test completed in 147 seconds with a 95% connection-failure
rate (3,304 successes out of 64,800 attempts). KEDA did fire and new nodes did
join, but most connections had already reset by then. Use 8–10 req/s for a clean
autoscaling ramp that lets you watch the full scale-up/down cycle.
:::

`aiperf` renders a TUI showing live TTFT, throughput, and concurrency. While it
runs, watch the autoscaling chain in separate terminals:

```bash
# Watch KEDA HPA adjust replica count
kubectl get hpa -n dynamo-cloud -w

# Watch decode worker pods come up
kubectl get pods -n dynamo-cloud -w

# Watch new H100 nodes join
kubectl get nodes -l agentpool=h100pool -w
```

What you should see:

1. Within 30–60 seconds of load starting, TTFT p99 crosses 300 ms.
2. KEDA marks the ScaledObject `ACTIVE=True` and increments the HPA desired count.
3. The Dynamo operator creates new `VllmDecodeWorker` pods.
4. If all GPUs are occupied, the cluster autoscaler adds a second (or third)
   `NC40ads_H100_v5` node. The new node takes ~3 minutes to become `Ready`.
5. New decode pods schedule on the fresh node, models load (~90 seconds for
   Qwen3-0.6B), and TTFT starts falling.
6. Once load drops and TTFT falls below threshold for the 120-second cooldown, KEDA
   scales down and the cluster autoscaler eventually removes idle GPU nodes.

### Observed Results

The following table shows the metrics from a 2-worker baseline run with
`Qwen/Qwen3-0.6B` under a 3,000-token synthetic workload. KEDA triggered within
the first polling interval (30 seconds) and the HPA scaled to 4 workers:

| Metric | Value |
|---|---|
| Successful requests | 3,304 |
| TTFT avg | 30,346 ms |
| TTFT p99 | 53,131 ms |
| TTFT p50 | 30,703 ms |
| Request latency avg | 45,013 ms |
| Output throughput | 5,593 tok/s |
| Request throughput | 22.38 req/s |
| Benchmark duration | 147 s |

The Grafana vLLM dashboard confirmed the signal: GPU KV cache hit 96.7% saturation
and the scheduler had 349 requests waiting before new workers came online.

## Cleanup

```bash
kubectl delete namespace dynamo-cloud
kubectl delete namespace dynamo-system
kubectl delete namespace keda
az identity delete \
  --name keda-prometheus-reader \
  --resource-group "${RESOURCE_GROUP}"
# To delete the entire cluster:
az group delete --name "${RESOURCE_GROUP}" --yes --no-wait
```

## Conclusion

TTFT-driven autoscaling changes the economics of GPU inference. Instead of
provisioning for peak load, you run a minimum viable fleet and let the cluster
expand only when latency actually degrades — with a direct causal link from the
user-facing SLO to the scale decision.

The key pieces that make this work on AKS:

* **AKS Managed GPU** removes the GPU Operator from the operational surface. Node
  pools with `--enable-managed-gpu` get drivers, device plugin, and DCGM
  automatically.
* **Dynamo's DynamoGraphDeploymentScalingAdapter** exposes a `scale` subresource on
  the decode worker tier, which KEDA can target just like a Deployment.
* **Azure Workload Identity** + **Azure Managed Prometheus** gives KEDA a
  secretless, fully managed path to the metric — no Prometheus passwords to rotate,
  no self-hosted metric stack.
* **Cluster Autoscaler** on the GPU pool closes the loop: when KEDA wants more pods
  than GPUs are available, new nodes join without manual intervention.

## References

- [NVIDIA Dynamo — Kubernetes installation guide](https://github.com/ai-dynamo/dynamo/blob/main/docs/kubernetes/installation-guide.md)
- [NVIDIA Dynamo on AKS — deployment guide](https://github.com/ai-dynamo/dynamo/blob/main/examples/deployments/AKS/AKS-deployment.md)
- [KEDA Prometheus scaler](https://keda.sh/docs/latest/scalers/prometheus/)
- [KEDA Azure Workload Identity authentication](https://keda.sh/docs/latest/concepts/authentication/#azure-workload-identity)
- [AKS Managed GPU nodes](https://learn.microsoft.com/azure/aks/aks-managed-gpu-nodes)
- [Azure Managed Prometheus overview](https://learn.microsoft.com/azure/azure-monitor/essentials/prometheus-metrics-overview)
- [Azure Managed Grafana — connect to data sources privately](https://learn.microsoft.com/azure/managed-grafana/how-to-connect-to-datasource-privately)
- [AKS Workload Identity overview](https://learn.microsoft.com/azure/aks/workload-identity-overview)
