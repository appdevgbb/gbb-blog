---
authors:
- diego_casati
date: '2025-01-31'
description: A procedure on how to update an AKS cluster network plugin, from Kubenet
  to Azure CNI Overlay Mode.
tags: []
title: Updating AKS Network Plugin from Kubenet to Azure CNI
---

# Updating AKS Network Plugin from Kubenet to Azure CNI

## Problem Statement

When updating an Azure Kubernetes Service (AKS) network plugin from **kubenet** to **Azure CNI**, performing the update directly using **Terraform** may result in the cluster being deleted and recreated. The Terraform plan typically indicates that the cluster will be replaced.

However, using **Azure CLI (az cli)**, the update can be successfully applied without deleting the cluster. Once that's done, you can import the state of the cluster back to terraform.

A validated approach to avoid cluster recreation involves the following steps:

- Perform the **CNI update** out-of-band using **Azure CLI**.
- **Import the state** of the cluster back to Terraform.
- Perform a **Terraform refresh** and a **Terraform plan** to validate the new state.

<!-- truncate -->

## Procedure

### **Step 1: Perform the upgrade using Azure CLI**

```bash
export clusterName=aks-kubenet-cluster
export resourceGroup=aks-kubenet-rg

az aks update --name $clusterName \
  --resource-group $resourceGroup \
  --network-plugin azure \
  --network-plugin-mode overlay
```
While is happening, AKS will create a new node, updated with the new network options. Once that is done, the older nodes will be removed, and eventually the entire cluster will be updated.

![AKS nodes](/img/2025-01-31-updating-aks-network-plugin-from-kubenet-to-azure-cni/portal.jpg)

### **Step 2: Modify Terraform Configuration**

Update the Terraform configuration to reflect the new **Azure CNI** network plugin settings.

```
  network_profile {
    network_plugin = "azure"
    network_plugin_mode = "overlay"
  }
```

### **Step 3: Import the new cluster state into Terraform**

```bash
terraform import azurerm_kubernetes_cluster.aks \
  "/subscriptions/6edaa0d4-86e4-431f-a3e2-d027a34f03c9/resourceGroups/aks-kubenet-rg/providers/Microsoft.ContainerService/managedClusters/aks-kubenet-cluster"
```

### **Step 4: Run Terraform Refresh and Plan**

```bash
terraform refresh
terraform plan
```

This ensures that Terraform recognizes the new state of the AKS cluster without attempting to recreate it.

## Conclusion

By following this approach, it is possible to transition an **AKS network plugin from kubenet to Azure CNI** while avoiding unnecessary cluster deletion and recreation.