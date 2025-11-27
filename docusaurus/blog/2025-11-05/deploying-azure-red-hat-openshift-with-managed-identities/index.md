---
authors:
- diego_casati
date: '2025-11-05'
description: A comprehensive guide to deploying Azure Red Hat OpenShift (ARO) clusters using managed identities.
tags: []
title: Deploying Azure Red Hat OpenShift with Managed Identities
---

# Deploying Azure Red Hat OpenShift with Managed Identities

When deploying **Azure Red Hat OpenShift (ARO)** clusters, managing authentication and authorization for various cluster components traditionally relies on service principals or other credential-based approaches. This introduces operational overhead and potential security risks related to credential rotation and management.

<!-- truncate -->

:::warning Preview Feature
This guide covers Azure Red Hat OpenShift managed identities, which is currently in **preview** and **not meant for production use**. Preview features are provided "as is" and excluded from service-level agreements. For production deployments, refer to [ARO's supported configurations](https://learn.microsoft.com/en-us/azure/openshift/).
:::

The **managed identity** approach is an alternative that provides core operators with short-term, auto-rotating credentials following the principle of least privilege, reducing the need to manage long-lived secrets or service principal credentials.

This guide demonstrates a comprehensive procedure to deploy ARO using managed identities, which offers:

- **Enhanced security** through automatic, short-term credential rotation and least privilege access
- **Simplified management** - Azure automatically handles credential lifecycle
- **Eight core operators** with minimal, scoped permissions for cluster infrastructure


## Prerequisites

Before deploying, ensure you have:

- **Azure CLI**: Version 2.76.0 (important: v2.77.0 has compatibility issues with ARO preview features)
- **jq**: JSON processor for parsing CLI output
- **Azure subscription** with appropriate permissions (Contributor role recommended)
- **Red Hat pull secret** (optional but recommended for full functionality)
- **Sufficient quota**: Minimum 44 vCPU cores in Standard DSv5 Family

### Known Issues

**Azure CLI Version Compatibility**: As of September 2025, Azure CLI v2.77.0 has a known issue causing API version conflicts with ARO preview features. You **must use Azure CLI v2.76.0**.

To downgrade on Debian/Ubuntu:

```bash
# Check current version
az version

# Downgrade to v2.76.0
sudo apt-get install azure-cli=2.76.0-1~noble

# Verify
az version
```

## Procedure

### **Step 1: Prepare the Deployment Script**

Clone the repository and configure the script:

```bash
git clone https://github.com/dcasati/aro-managed-identity.git
cd aro-managed-identity
chmod +x deploy-aro-managed-identity.sh
```

### **Step 2: Obtain Red Hat Pull Secret**

1. Visit [Red Hat OpenShift on Azure (ARO)](https://console.redhat.com/openshift/install/azure/aro-provisioned)
2. Download your pull secret
3. Save it as `pull-secret.txt` in the same directory as the script

### **Step 3: Set Environment Variables**

Configure your deployment parameters:

```bash
export LOCATION=westus3                    # Azure region
export RESOURCEGROUP=aro-rg-westus3       # Resource group name
export CLUSTER=aro-cluster                 # Cluster name
export CLUSTER_VERSION=4.15.35            # ARO version
export PULL_SECRET_FILE=pull-secret.txt   # Pull secret file path
```

### **Step 4: Validate Dependencies**

Before proceeding with deployment, verify all dependencies are installed:

```bash
./deploy-aro-managed-identity.sh -x check-deps
```

The script will verify:
- Azure CLI installation and version (must be 2.76.0)
- jq availability
- Quota requirements (44+ cores)
- Resource providers registration

### **Step 5: Deploy the Cluster**

Initiate the ARO deployment with managed identities:

```bash
./deploy-aro-managed-identity.sh -x install
```

The deployment script will automatically:
1. Check dependencies and Azure CLI version
2. Install the ARO preview extension
3. Register required resource providers (Microsoft.RedHatOpenShift, Microsoft.Compute, Microsoft.Storage, Microsoft.Authorization)
4. Validate quota requirements
5. Create the resource group
6. Create virtual network and subnets (10.0.0.0/22 with master and worker subnets)
7. Create 9 managed identities for cluster components
8. Assign comprehensive RBAC roles
9. Deploy the ARO cluster with managed identity assignments

**Expected deployment time**: 45-55 minutes

### **Step 6: Access Your Cluster**

Once deployment completes, retrieve cluster information and credentials:

```bash
./deploy-aro-managed-identity.sh -x show
```

This command will display:
- OpenShift Console URL
- API Server URL
- Provisioning state
- Admin credentials (username and password)

## What Gets Created

### Managed Identities (9 total)

Azure Red Hat OpenShift requires 9 user-assigned managed identities: 8 core operator identities and 1 cluster identity for federated credential management.

**Core Operators (8):**

| Identity | Purpose |
|----------|---------|
| `image-registry` | OpenShift Image Registry Operator - manages container image registry |
| `cloud-network-config` | OpenShift Network Operator - manages cluster networking configuration |
| `disk-csi-driver` | OpenShift Disk Storage Operator - provisions Azure Disk storage |
| `file-csi-driver` | OpenShift File Storage Operator - provisions Azure Files storage |
| `ingress` | OpenShift Cluster Ingress Operator - manages ingress controller |
| `cloud-controller-manager` | OpenShift Cloud Controller Manager - integrates with Azure cloud provider |
| `machine-api` | OpenShift Machine API Operator - manages node scaling and lifecycle |
| `aro-operator` | Azure Red Hat OpenShift Service Operator - handles ARO-specific operations |

**Cluster Identity (1):**

| Identity | Purpose |
|----------|---------|
| `aro-cluster` | Azure Red Hat OpenShift Cluster Identity - enables core operator identities and performs federated credential creation |

### Network Resources

- **Virtual Network**: `aro-vnet` (10.0.0.0/22)
- **Master Subnet**: `master` (10.0.0.0/23) - for OpenShift control plane
- **Worker Subnet**: `worker` (10.0.2.0/23) - for application workloads

### RBAC Assignments

The script creates 12+ role assignments including:
- Cluster identity permissions to manage other identities
- Network-level permissions for operators on subnets
- VNet-level permissions for storage and network components
- Delegation permissions for platform workload identity

## Cluster Operations

### Get Cluster Information

Retrieve current cluster status and credentials at any time:

```bash
./deploy-aro-managed-identity.sh -x show
```

### Clean Up Resources

When finished, remove all resources:

```bash
./deploy-aro-managed-identity.sh -x destroy
```

This will:
1. Delete the ARO cluster
2. Remove all 9 managed identities
3. Delete the entire resource group and all associated resources

### Troubleshooting

#### Common Issues

**Quota Exceeded**
```bash
# Check available quota
az vm list-usage -l westus3 --query "[?contains(name.value, 'standardDSv5Family')]" -o table
```
Request quota increase for Standard DSv5 Family vCPUs if needed.

**Permission Denied**
Ensure you have Contributor role on the subscription:
```bash
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

**Resource Provider Not Registered**
```bash
# Check provider status
az provider list --query "[?contains(namespace, 'RedHat')||contains(namespace, 'Compute')||contains(namespace, 'Storage')]" -o table
```

**List Existing Clusters**
```bash
az aro list -o table
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LOCATION` | `eastus` | Azure region for deployment |
| `RESOURCEGROUP` | `aro-rg` | Resource group name |
| `CLUSTER` | `cluster` | ARO cluster name |
| `CLUSTER_VERSION` | `4.15.35` | OpenShift version to deploy |
| `PULL_SECRET_FILE` | `pull-secret.txt` | Path to Red Hat pull secret |

## Architecture & Security Benefits

The **managed identity approach** provides the following advantages for managing operator credentials:

- **Short-term Credentials**: Credentials are automatically rotated with a short duration, reducing exposure window
- **Principle of Least Privilege**: Each operator identity is granted only the minimum permissions required for its specific tasks
- **No Secret Management**: Eliminates the need to manage, rotate, or store long-lived credentials or secrets
- **Federated Credentials**: The `aro-cluster` identity manages federated credential creation for all 8 core operators

## Conclusion

By following this procedure, you can deploy an **Azure Red Hat OpenShift cluster with managed identities** for operator credential management. The automated script handles the complexity of creating 9 managed identities and configuring 12+ RBAC role assignments.

**Important**: Remember that this feature is currently in preview and not recommended for production use. For production deployments, use standard ARO configurations and refer to [Azure Red Hat OpenShift documentation](https://learn.microsoft.com/en-us/azure/openshift/).

For issues or questions:
- **ARO Service**: Contact Microsoft Azure Support
- **OpenShift Platform**: Contact Red Hat Support
- **This Script**: Open an issue at [dcasati/aro-managed-identity](https://github.com/dcasati/aro-managed-identity)
