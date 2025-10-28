---
authors:
- steve_griffith
date: '2024-04-16'
description: Setting up an AKS cluster with the Kubernetes AI Toolchain Operator (KAITO)
  managed add-on and then deploying an inference model from your own private Azure
  Containter Registry.
tags: []
title: Using Project KAITO in AKS
---

# Project KAITO and the AKS Managed Add-on

The Kubernetes AI Toolchain Operator, also known as Project KAITO, is an open-source solution to simplify the deployment of inference models in a Kubernetes cluster. In particular, the focus is on simplifying the operation of the most popular models available (ex. Falcon, Mistral and Llama2).

KAITO provides operators to manage validation of the requested model against the requested nodepool hardware, deployment of the nodepool and the deployment of the model itself along with a REST endpoint to reach the model.

<!-- truncate -->

In this walkthrough we'll deploy an AKS cluster with the KAITO managed add-on. Next, we'll deploy and test an inference  model, which we'll pull from our own private container registry. We'll be following the setup guide from the AKS product docs [here](https://learn.microsoft.com/en-us/azure/aks/ai-toolchain-operator) with some of my own customizations and extensions to simplify tasks.

## Cluster Creation

In this setup we'll be creating a very basic AKS cluster via the [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/), but this managed add-on will work in any AKS cluster, assuming you meet the [pre-reqs](https://learn.microsoft.com/en-us/azure/aks/ai-toolchain-operator#prerequisites). 

We'll also be creating an Azure Container Registry to demonstrate replicating a KAITO model to your own private registry and using it in the model deployment, which would be a security best practice.

```bash
# Set Variables
RG=KaitoLab
LOC=westus3
ACR_NAME=kaitolab
CLUSTER_NAME=kaito

# Create the resource group
az group create -n $RG -l $LOC

# Create the Azure Container Registry
az acr create -g $RG -n $ACR_NAME --sku Standard

# Create the AKS Cluster
az aks create \
-g $RG \
-n $CLUSTER_NAME \
--enable-oidc-issuer \
--enable-ai-toolchain-operator

# Get the Cluster Credentials
az aks get-credentials -g $RG -n $CLUSTER_NAME
```

## Setup the KAITO Identity

KAITO uses the node auto-provisioner to add nodepools to the AKS cluster. To do this it needs rights on the cluster resource group. At this time the rights are broad, but as KAITO reaches general availabiliy we should see those roles refined.

```bash
# Get the Cluster Resource Group
export RG_ID=$(az group show -n $RG -o tsv --query id)

# Get the managed cluster Resource Group
export MC_RESOURCE_GROUP=$(az aks show --resource-group ${RG} --name ${CLUSTER_NAME} --query nodeResourceGroup -o tsv)

# Set a variable for the KAITO IDentity name
export KAITO_IDENTITY_NAME="ai-toolchain-operator-${CLUSTER_NAME}"

# Get the principal ID for the KAITO managed identity
export PRINCIPAL_ID=$(az identity show --name "${KAITO_IDENTITY_NAME}" --resource-group "${MC_RESOURCE_GROUP}" --query 'principalId' -o tsv)

# Grant contributor on the cluster resource group
az role assignment create --role "Contributor" --assignee "${PRINCIPAL_ID}" --scope $RG_ID

# Get the OIDC Issuer URL
export AKS_OIDC_ISSUER=$(az aks show --resource-group "${RG}" --name "${CLUSTER_NAME}" --query "oidcIssuerProfile.issuerUrl" -o tsv)

# Create the federation between the KAITO service account and the KAITO Azure Managed Identity
az identity federated-credential create --name "kaito-federated-identity" --identity-name "${KAITO_IDENTITY_NAME}" -g "${MC_RESOURCE_GROUP}" --issuer "${AKS_OIDC_ISSUER}" --subject system:serviceaccount:"kube-system:kaito-gpu-provisioner" --audience api://AzureADTokenExchange

# If you check the kaito-gpu-provisioner pod, you'll see it's in CrashLoopBackOff
# due to the identity not yet having been configured with proper rights.
kubectl get pods -l app=ai-toolchain-operator -n kube-system

# Restart the GPU provisioner to reload authorization
kubectl rollout restart deployment/kaito-gpu-provisioner -n kube-system

# Check the pod again to confirm it's now running
kubectl get pods -l app=ai-toolchain-operator -n kube-system
```

## Set up the Azure Container Registry

The KAITO team builds and hosts the most popular inference models for you. These models are available in the Microsoft Container Registry (MCR) and if you run a KAITO workspace for one of those models it will pull that image for you automatically. However, as noted above, security best practice is to only pull images from your own trusted repository. Fortunately, KAITO gives you this option.

Let's pull the image from the MCR into our Azure Container Registry, and link that registry to our AKS cluster. The image for the model in the MCR follows a standard format, as seen below. We just need the model name and version and we can import it into our private registry. We'll use Mistral-7B.

>**NOTE:** If you aren't already aware, Large Language Models are LARGE. This import will take some time. Assume 10-20 minutes for many models.

```bash
MODELNAME=mistral-7b-instruct
TAG="0.0.2"

# Copy over the mistral image to our ACR
az acr import -g $RG --name $ACR_NAME --source  mcr.microsoft.com/aks/kaito/kaito-$MODELNAME:$TAG --image $MODELNAME:$TAG
```

While the import is running, we can go ahead and start another terminal window to attach the Azure Container Registry to our AKS cluster. 

We don't need to attach the ACR, if we prefer to use admin credentials and an image pull secret, but using the attach feature is more secure as it authenticates to ACR with the kubelet managed identity.

```bash
# If we're in a new terminal window we'll need to set our environment variables
RG=KaitoLab
CLUSTER_NAME=kaitocluster
ACR_NAME=kaitolab

# Attach the ACR
az aks update -g $RG -n $CLUSTER_NAME --attach-acr $ACR_NAME
```

## Deploy a model!

Now that our cluster and registry are all set, we're ready to deploy our first model. We'll generate our 'Workspace' manifest ourselves, but you can also pull from the [examples](https://github.com/Azure/kaito/blob/main/presets/README.md) in the KAITO repo and update as needed. The model below is actually directly from the examples; however I added the 'presetOptions' section to set the source of the model image.

>**NOTE:** Make sure you validate you have quota on the target subscription for the machine type you select below.

```bash
# Set the target machine size
MACHINE_SIZE=Standard_NC64as_T4_v3

# Generate the model manifest
cat <<EOF >${MODELNAME}-${TAG}.yaml
apiVersion: kaito.sh/v1alpha1
kind: Workspace
metadata:
  name: workspace-${MODELNAME}
resource:
  instanceType: "${MACHINE_SIZE}"
  labelSelector:
    matchLabels:
      apps: ${MODELNAME}
inference:
  preset:
    name: "${MODELNAME}"
    presetOptions:
      image: ${ACR_NAME}.azurecr.io/${MODELNAME}:${TAG}
EOF

# OPTIONAL: In another terminal, if you wish, watch the gpu and workspace provisioner logs
kubectl logs -f -l app=ai-toolchain-operator -n kube-system

# Deploy Mistral
kubectl apply -f ${MODELNAME}-${TAG}.yaml

# Watch the deployment 
# This will take some time as the node provisions and the model is pulled
watch kubectl get workspace,nodes,svc,pods
```

## Test your inference endpoint

Now that our model is running, we can send it a request. By default, the model is only accessible via a ClusterIP inside the Kubernetes cluster, so you'll need to access the endpoint from a test pod. We'll use a public 'curl' image, but you can use whatever you prefer.

You do have the option to expose the model via a Kubernetes Service of type 'LoadBalancer' via the workspace configuration, but that generally isn't recommended. Typically, you'd be calling the model from another service inside the cluster, or placing the endpoint behind an ingress controller.

```bash
# Get the model cluster IP
CLUSTERIP=$(kubectl get svc workspace-${MODELNAME} -o jsonpath='{.spec.clusterIP}')

# Curl the model service
kubectl run -it --rm --restart=Never curl --image=curlimages/curl -- \
curl -X POST http://$CLUSTERIP/chat \
-H "accept: application/json" \
-H "Content-Type: application/json" \
-d "{\"prompt\":\"Who is Inigo Montoya and from what movie?\",\"generate_kwargs\":{\"max_length\":200}}"
```

## Conclustion

Congratulations! You should now have a working AKS cluster with the Kubernetes AI Toolchain Operator up and running. As you explore KAITO please feel free to reach out to the KAITO team via the [open-source project](https://github.com/Azure/kaito/issues) for any questions or feature requests.

