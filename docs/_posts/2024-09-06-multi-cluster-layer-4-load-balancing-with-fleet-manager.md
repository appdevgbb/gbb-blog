---
title: Multi-Cluster Layer 4 Load Balancing with Fleet Manager
description: How to configure a multi-cluster layer 4 load balancer across multiple AKS clusters using Fleet Manager.

authors: 
  - diego_casati
---

Updates: 
  - 2025-02-11: Major changes to the post bringing more clarity after peer review. Thanks @awkwardindustries and Joe Yostos!
  - 2025-02-13: Fix some command line issues.

# Multi-Cluster Layer 4 Load Balancing with Fleet Manager
This guide demonstrates how to set up layer 4 load balancing across multiple AKS clusters using 
Azure Fleet Manager. We’ll create two AKS clusters in different regions (East US and West US), 
configure Virtual Network (VNet) peering between them, and deploy a demo application using 
Fleet Manager. The process covers AKS cluster setup, VNet peering, Fleet Manager configuration, 
and application deployment across regions.


### Topology

```
+-----------------------+          +-----------------------+
|    AKS Cluster (East) |          |    AKS Cluster (West) |
|  Region: East US      |          |  Region: West US      |
|                       |          |                       |
| +-------------------+ |          | +-------------------+ |
| |   Application     | |          | |   Application     | |
| +-------------------+ |          | +-------------------+ |
|                       |          |                       |
+-----------------------+          +-----------------------+
          |                                      |
          +--------------------------------------+
                        VNet Peering

             +-----------------------------------+
             |    Fleet Manager (Hub Region)     |
             +-----------------------------------+
```

- [x] AKS Cluster (East): A Kubernetes cluster deployed in the East US region.
- [x] AKS Cluster (West): A Kubernetes cluster deployed in the West US region.
- [x] VNet Peering: Virtual Network peering between the AKS clusters to enable communication.
- [x] Fleet Manager: Azure Fleet Manager deployed in the hub region, managing the application across both AKS clusters.

### Create two AKS clusters

For this demo, we will create two AKS clusters in two regions: East and West.

#### Create the cluster in East US

The first step is to setup all of the environment variables that we will use
```bash
# ======================
# Environment Variables
# ======================
export LOCATION_EAST="eastus2"
export LOCATION_WEST="westus2"
export RESOURCE_GROUP_EAST="rg-aks-$LOCATION_EAST"
export RESOURCE_GROUP_WEST="rg-aks-$LOCATION_WEST"
export CLUSTER_EAST="aks-$LOCATION_EAST"
export CLUSTER_WEST="aks-$LOCATION_WEST"
export FLEET_RESOURCE_GROUP_NAME="rg-fleet"
export FLEET="gbb-fleet"
export FLEET_LOCATION="westus"

# VNET
export VNET_EAST="aks-vnet-east"
export VNET_WEST="aks-vnet-west"
export VNET_EAST_PREFIX="10.1.0.0/16"
export VNET_WEST_PREFIX="10.2.0.0/16"

# Non-overlapping CIDR ranges
export CIDR_EAST="10.1.0.0/24"
export CIDR_WEST="10.2.0.0/24"

# Subnet names
export SUBNET_EAST="aks-subnet-east"
export SUBNET_WEST="aks-subnet-west"
```

We can now proceed with the creation of the first cluster

```bash
# Create a resource group for the cluster in East US
az group create \
  --name ${RESOURCE_GROUP_EAST} \
  --location ${LOCATION_EAST}

# Create a vNet for the West US cluster
az network vnet create \
  --resource-group ${RESOURCE_GROUP_EAST} \
  --name ${VNET_EAST} \
  --address-prefix ${VNET_EAST_PREFIX} \
  --subnet-name ${SUBNET_EAST} \
  --subnet-prefix ${CIDR_EAST}

# Retrieve the subnet id
SUBNET_ID_EAST=$(az network vnet subnet show \
  --resource-group ${RESOURCE_GROUP_EAST} \
  --vnet-name ${VNET_EAST} \
  --name ${SUBNET_EAST} \
  --query "id" -o tsv)

# Create an AKS cluster with Azure CNI
az aks create \
  --resource-group ${RESOURCE_GROUP_EAST} \
  --name ${CLUSTER_EAST} \
  --network-plugin azure \
  --vnet-subnet-id ${SUBNET_ID_EAST} \
  --generate-ssh-keys


# get the cluster credentials (East US)
az aks get-credentials \
  --resource-group ${RESOURCE_GROUP_EAST} \
  --name ${CLUSTER_EAST} \
  --file ${CLUSTER_EAST}
```

Now repeat the same process for the cluster in West US:

```bash
# Create a resource group for the cluster in West US
az group create \
  --name ${RESOURCE_GROUP_WEST} \
  --location ${LOCATION_WEST}

# Create a vNet for the West US cluster
az network vnet create \
  --resource-group ${RESOURCE_GROUP_WEST} \
  --name ${VNET_WEST} \
  --address-prefix ${VNET_WEST_PREFIX} \
  --subnet-name ${SUBNET_WEST} \
  --subnet-prefix ${CIDR_WEST}

# Retrieve the subnet id
SUBNET_ID_WEST=$(az network vnet subnet show \
  --resource-group ${RESOURCE_GROUP_WEST} \
  --vnet-name ${VNET_WEST} \
  --name ${SUBNET_WEST} \
  --query "id" -o tsv)

# Create an AKS cluster with Azure CNI
az aks create \
  --resource-group ${RESOURCE_GROUP_WEST} \
  --name ${CLUSTER_WEST} \
  --network-plugin azure \
  --vnet-subnet-id ${SUBNET_ID_WEST} \
  --generate-ssh-keys

# get the cluster credentials (West US)
az aks get-credentials \
  --resource-group ${RESOURCE_GROUP_WEST} \
  --name ${CLUSTER_WEST} \
  --file ${CLUSTER_WEST}
```
#### Create the VNets and peer them
Peer the VNets between East and West US:

```bash
# Peer VNets between East and West
VNET_ID_EAST=$(az network vnet show --resource-group ${RESOURCE_GROUP_EAST} --name ${VNET_EAST} --query "id" -o tsv)
VNET_ID_WEST=$(az network vnet show --resource-group ${RESOURCE_GROUP_WEST} --name ${VNET_WEST} --query "id" -o tsv)

# Create VNet peering from east to west
az network vnet peering create --name EastToWestPeering \
    --resource-group ${RESOURCE_GROUP_EAST} \
    --vnet-name ${VNET_EAST} \
    --remote-vnet ${VNET_ID_WEST} \
    --allow-vnet-access

# Create VNet peering from west to east
az network vnet peering create --name WestToEastPeering \
    --resource-group ${RESOURCE_GROUP_WEST} \
    --vnet-name ${VNET_WEST} \
    --remote-vnet ${VNET_ID_EAST} \
    --allow-vnet-access
```
#### Create a Fleet Manager and add members to it
Add the fleet extension to Azure CLI

```bash
az extension add --name fleet
```

Create the Fleet Manager resource

```bash
# create the resource group
az group create \
  --name ${FLEET_RESOURCE_GROUP_NAME} \
  --location ${FLEET_LOCATION}

# create fleet resource
az fleet create \
  --resource-group ${FLEET_RESOURCE_GROUP_NAME} \
  --name ${FLEET} \
  --location ${FLEET_LOCATION} \
  --enable-hub

# Fleet Manager credentials
az fleet get-credentials \
  --resource-group ${FLEET_RESOURCE_GROUP_NAME} \
  --name ${FLEET} \
  --file ${FLEET}

FLEET_ID=$(az fleet show --resource-group "$FLEET_RESOURCE_GROUP_NAME" --name "$FLEET" -o tsv --query=id)

IDENTITY=$(az ad signed-in-user show --query "id" --output tsv)
ROLE="Azure Kubernetes Fleet Manager RBAC Cluster Admin"
az role assignment create \
  --role "$ROLE" \
  --assignee "$IDENTITY" \
  --scope ${FLEET_ID}
```

Retrieve the Cluster IDs for East and West clusters:

```bash
# Retrieve Cluster IDs (East and West)
export AKS_EAST_ID=$(az aks show --resource-group ${RESOURCE_GROUP_EAST} --name ${CLUSTER_EAST} --query "id" -o tsv)

export AKS_WEST_ID=$(az aks show --resource-group ${RESOURCE_GROUP_WEST} --name ${CLUSTER_WEST} --query "id" -o tsv)

echo "AKS EAST cluster id: ${AKS_EAST_ID}"
echo "AKS WEST cluster id: ${AKS_WEST_ID}"
```

Now join both clusters to the Fleet:

```bash
# join the East US cluster
az fleet member create \
  --resource-group ${FLEET_RESOURCE_GROUP_NAME} \
  --fleet-name ${FLEET} \
  --name ${CLUSTER_EAST} \
  --member-cluster-id ${AKS_EAST_ID}

# join the West US cluster
az fleet member create \
  --resource-group ${FLEET_RESOURCE_GROUP_NAME} \
  --fleet-name ${FLEET} \
  --name ${CLUSTER_WEST} \
  --member-cluster-id ${AKS_WEST_ID}
```

Check if everything was setup correctly 
```bash
KUBECONFIG=${FLEET} kubectl get memberclusters
```

You should see an output similar to this:

```bash
NAME          JOINED   AGE     MEMBER-AGENT-LAST-SEEN   NODE-COUNT   AVAILABLE-CPU   AVAILABLE-MEMORY
aks-eastus2   True     11m     5s                       3            4196m           17827580Ki
aks-westus2   True     9m24s   11s                      3            4196m           17827580Ki
```
#### Deploy the AKS store application

For this next step, we will deploy the AKS Store demo application to both clusters, 
East and West, using Fleet. Fleet Manager will work as a centralized hub, sending the
configuration and deployment files to its member clusters.

```bash
# create the namespace for the application
KUBECONFIG=${FLEET} kubectl create ns aks-store-demo

# deploy the application on both clusters thru Fleet
KUBECONFIG=${FLEET} kubectl apply -n aks-store-demo -f  https://raw.githubusercontent.com/Azure-Samples/aks-store-demo/main/aks-store-ingress-quickstart.yaml
```

Let's pause for a moment and see what we have done. At this stage, we have done the following:

- Two AKS cluster, one in East US and another in West US.
- We have connected the vNets of these two clusters using vNet Peering.
- A hub AKS Fleet Manager was deployed and the two clusters were added as its members. 
- The AKS Store Demo application was deployed on both clusters (East US and West US) through Fleet.

Our next step now is to leverage three components from AKS Fleet Manager: Service Export, Multi Cluster Service and Cluster Resource Placement.

| Feature | Purpose | Use Case | How It Works |
|-|-|-|-|
| **ServiceExport** | Exports a service from a member cluster to other clusters as a Fleet resource. This can then be used for cross-cluster service load balancing. | Exposing a backend service from Cluster A to Cluster B within the AKS Fleet. | A Kubernetes service is marked as "exported" so it can be discovered and imported by other clusters. e.g.: exporting the `store-front` service from the `aks-store-demo` namespace |
| **ClusterResourcePlacement** | Allows the deployment of Kubernetes resources across fleet members. | Automatically deploying an application, config maps, or secrets to all clusters in a region. | Selects target member clusters based on labels and ensures the specified resources are synchronized across them. e.g.: match on `fleet.azure.com/location` being `eastus2` or `westus2` |
| **MultiClusterService** | A resource that allows the user to setup a Layer 4 multi-cluster load balancing solution across the fleet. | Load balancing requests to a frontend service running in multiple AKS clusters. | Automatically detects exported services and provides a unified endpoint that distributes traffic across clusters. e.g.: expose the `store-front` service |

Create the Service Export:

```bash
cat <<EOF > aks-store-serviceexport.yaml
apiVersion: networking.fleet.azure.com/v1alpha1
kind: ServiceExport
metadata:
  name: store-front
  namespace: aks-store-demo
EOF

KUBECONFIG=${FLEET} kubectl apply -n aks-store-demo -f aks-store-serviceexport.yaml
```

Verify that the service export was deployed:

```bash
KUBECONFIG=${FLEET} kubectl -n aks-store-demo get serviceexport
```

You should see an output similar to this:

```bash
NAME          IS-VALID   IS-CONFLICTED   AGE
store-front                              2m4s
```

Create the ClusterResourcePlacement (CRP):

```bash
cat <<EOF > cluster-resource-placement.yaml
apiVersion: placement.kubernetes-fleet.io/v1beta1
kind: ClusterResourcePlacement
metadata:
  name: aks-store-demo
spec:
  resourceSelectors:
    - group: ""
      version: v1
      kind: Namespace
      name: aks-store-demo
  policy:
    affinity:
      clusterAffinity:
        requiredDuringSchedulingIgnoredDuringExecution:
          clusterSelectorTerms:
            - labelSelector:
                matchExpressions:
                  - key: fleet.azure.com/location
                    operator: In
                    values:
                      - ${LOCATION_EAST}
                      - ${LOCATION_WEST}
EOF

KUBECONFIG=${FLEET} kubectl apply -f cluster-resource-placement.yaml
```
Verify that the CRP was created:

```bash
KUBECONFIG=${FLEET} kubectl get ClusterResourcePlacement
NAME             GEN   SCHEDULED   SCHEDULED-GEN   AVAILABLE   AVAILABLE-GEN   AGE
aks-store-demo   2     True        2               True        2               110s
```

Create and deploy MultiClusterService (MCS):

```bash
cat <<EOF > aks-store-mcs.yaml
apiVersion: networking.fleet.azure.com/v1alpha1
kind: MultiClusterService
metadata:
  name: store-front
  namespace: aks-store-demo
spec:
  serviceImport:
    name: store-front
EOF

# Deploy the MultiClusterService resource to the East US cluster
KUBECONFIG=${CLUSTER_EAST} kubectl apply -f aks-store-mcs.yaml
```

Verify that the MCS was deployed and that the `IS_VALID` field is showing `True`:

```bash
KUBECONFIG=${CLUSTER_EAST} kubectl -n aks-store-demo get mcs
NAME          SERVICE-IMPORT   EXTERNAL-IP    IS-VALID   AGE
store-front   store-front      20.7.120.195   True       55s
```

#### Testing the Application

Once the MultiClusterService (MCS) has been successfully deployed across the AKS clusters, you can test the application to ensure it's working properly. Follow these steps to verify the setup:

**Get the external IP address of the service**:

After deploying the MultiClusterService, you need to retrieve the external IP address to access the service. Run the following command to get the external IP for the East-US cluster:

```bash
KUBECONFIG=${CLUSTER_EAST} kubectl get services -n fleet-system
```
Look for the external IP under the EXTERNAL-IP column for the store-front service.

**Access the application**:

Once you have the external IP addresses from both clusters, open a browser or use curl to access the application using the IP addresses:

```bash
curl http://<external-ip>
```

Replace <external-ip> with the actual external IP you retrieved from the previous step. The application should be accessible through either of the IPs.

Validate cross-region load balancing:

Since the `MultiClusterService` has been deployed across multiple regions, traffic can be balanced between the AKS clusters. You can simulate 
traffic from different regions using tools like curl, Postman, or load-testing utilities to confirm that the service is responding from both regions.

**Verify service status**:

You can check the status of the deployed services and pods on both clusters to ensure everything is running correctly:

```bash
KUBECONFIG=${CLUSTER_EAST} kubectl get pods -n aks-store-demo
KUBECONFIG=${CLUSTER_WEST} kubectl get pods -n aks-store-demo
```
Ensure that all services and pods show a Running status, indicating that the application is running across both clusters.

#### Remove the setup
To remove this setup, you can run the following set of commands:

```bash
# East cluster
az group delete --name ${RESOURCE_GROUP_EAST} --yes --no-wait

# West cluster
az group delete --name ${RESOURCE_GROUP_WEST} --yes --no-wait

# Fleet Hub
az group delete --name ${FLEET_RESOURCE_GROUP_NAME} --yes --no-wait
```

### Conclusion
In this guide, we successfully set up a multi-cluster layer 4 load balancer across 
AKS clusters using Azure Fleet Manager. By configuring AKS clusters in different regions, 
establishing VNet peering, and utilizing Fleet Manager, we enabled centralized management 
and deployment of services across clusters. This approach ensures improved availability and 
scalability for applications deployed across multiple regions.

For the full deployment script used in this tutorial, you can access 
the App Innovation GBB GitHub repository: [Pattern - Multi-Cluster Layer 4 Load Balancer with Azure Fleet Manager](https://github.com/appdevgbb/pattern-fleet-manager/tree/main).
