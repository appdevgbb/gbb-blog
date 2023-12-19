---
title: Using External DNS in AKS with Azure Workload Identity
description: The External DNS project supports auto record creation in both Azure public and Private DNS Zones. In this walk through we'll show how to configure an install External DNS in an AKS cluster using Workload Identity to update A records in an Azure Private DNS Zone
authors: 
  - steve_griffith
---

# External DNS with Azure Private Zones and Workload Identity

The following walk-through shows how to use the [External DNS](https://github.com/kubernetes-sigs/external-dns) project to monitor for services with DNS annotation to automatically create DNS records in an Azure Private Zone. The system user authorized to update the private zone will be an Azure Managed Identity, using AKS Workload Identity support.

### Set Environment Variables

Update the following with your own prefered values.

```bash
RG=EphExternalDNSDemo
LOC=eastus
AZURE_DNS_ZONE="griffdemo123.com" # DNS zone name like example.com or sub.example.com
CLUSTER_NAME=externaldns
TENANT_ID=$(az account show --query tenantId -o tsv)
SUB_ID=$(az account show --query id -o tsv)
```

### Create the Resource Group and Vnet

Now to create the resource group and Vnet which we will use for both the private zone and the AKS cluster. You can obviously substitute your own existing Vnet, but don't miss the next step where the private zone get's linked to the vnet.

```bash
# Create the Resource Group
az group create -n $RG -l $LOC

# Create the Vnet
az network vnet create \
--name testvnet \
--resource-group $RG \
--address-prefix 10.2.0.0/16 \
--subnet-name aks \
--subnet-prefixes 10.2.0.0/24

# Get the subnet id for later use
SUBNET_ID=$(az network vnet subnet show -g $RG --vnet-name testvnet -n aks -o tsv --query id)
```

### Create the Private DNS Zone

Now to create the private zone and link it to the vnet.

```bash
# Create the DNS Zone
az network private-dns zone create \
--resource-group $RG \
--name $AZURE_DNS_ZONE

# Link the private zone to the vnet
az network private-dns link vnet create \
-g $RG \
-n zonelink \
-z $AZURE_DNS_ZONE \
-v testvnet \
--registration-enabled false
```

### Create the AKS Cluster

We'll create the AKS cluster in the above created subnet, and enable the flags for Workload Identity Support (i.e. OIDC Issuer and Workload Identity). 

```bash
# Create the AKS Cluster
az aks create \
-g $RG \
-n $CLUSTER_NAME \
--vnet-subnet-id $SUBNET_ID \
--enable-oidc-issuer \
--enable-workload-identity \
--enable-managed-identity

# Get the cluster credentials
az aks get-credentials \
-g $RG \
-n $CLUSTER_NAME 
```

### Setup with Workload Identity

Azure Workload Identity for Kubernetes enables the finest grained control of the user that will be managing the DNS records, because we can isolate the rights specific to those needed to control the private zone. In the following steps, we'll get the OIDC issuer URL, create the managed identity, and create the Azure AD Federation for the service account used by external DNS.

>**NOTE:** In our setup we will assume external DNS resides in the 'default' namespace. If you move external DNS to it's own namespace, you'll need to make sure the 'az identity federated-credential create' command below references the right namespace in the fully qualified service account name in the '--subject' field. 

```bash
# Get the OIDC Issuer URL
export AKS_OIDC_ISSUER="$(az aks show -n $CLUSTER_NAME -g $RG --query "oidcIssuerProfile.issuerUrl" -otsv)"

# Create the managed identity
az identity create --name external-dns-identity --resource-group $RG --location $LOC

# Get identity client ID
export USER_ASSIGNED_CLIENT_ID=$(az identity show --resource-group $RG --name external-dns-identity --query 'clientId' -o tsv)

# Get the resource group ID
RG_ID=$(az group show -n $RG -o tsv --query id)

# Get the DNS Zone ID
DNS_ID=$(az network private-dns zone show --name $AZURE_DNS_ZONE \
 --resource-group $RG --query "id" --output tsv)

# Give the kubelet identity DNS Contributor rights
az role assignment create \
--assignee $USER_ASSIGNED_CLIENT_ID \
--role "Private DNS Zone Contributor" \
--scope "$DNS_ID"

az role assignment create \
--role "Reader" \
--assignee $USER_ASSIGNED_CLIENT_ID \
--scope $RG_ID

# Federate the identity
az identity federated-credential create \
--name external-dns-identity \
--identity-name external-dns-identity \
--resource-group $RG \
--issuer ${AKS_OIDC_ISSUER} \
--subject system:serviceaccount:default:external-dns

```


### Install External DNS

We'll install External DNS using it's helm chart, setting the values to ensure we're using the Azure Private DNS provider and pass in the managed identity details.

First, lets create the values file. 

>**NOTE:** We default to the 'debug' log level for testing, but you can remove that line to minimize logging once you're up and running. The default value for logLevel is 'info'.

```bash
cat <<EOF > values.yaml
fullnameOverride: external-dns

serviceAccount:
  annotations:
    azure.workload.identity/client-id: ${USER_ASSIGNED_CLIENT_ID}

podLabels:
  azure.workload.identity/use: "true"

provider: azure-private-dns

azure:
  resourceGroup: "${RG}"
  tenantId: "${TENANT_ID}"
  subscriptionId: "${SUB_ID}"
  useWorkloadIdentityExtension: true

logLevel: debug

EOF
```

Run the helm install.

```bash
# Add the helm repo
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update the helm repo in case you already have it
helm repo update bitnami

# Install external dns
helm install external-dns bitnami/external-dns -f values.yaml

```

### Test External DNS

Finally, lets make sure everything is working. We'll create a deployment and a service with both a private load balancer annotation and the annotation used by External DNS to trigger record creation.

```bash
# Test ExternalDNS
cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      annotations:
        external-dns.alpha.kubernetes.io/hostname: pod.griffdemo123.com
      labels:
        app: nginx
    spec:
      hostNetwork: true
      containers:
      - image: nginx
        name: nginx
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  annotations:
    service.beta.kubernetes.io/azure-load-balancer-internal: "true"
    external-dns.alpha.kubernetes.io/hostname: hello.griffdemo123.com
    external-dns.alpha.kubernetes.io/internal-hostname: hello-clusterip.griffdemo123.com
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: 80
  selector:
    app: nginx
  type: LoadBalancer
EOF
```

You can check the logs for external DNS as follows:

```bash
# To dump the current pod logs
kubectl logs -l app.kubernetes.io/instance=external-dns

# To follow the pod logs
kubectl logs -f -l app.kubernetes.io/instance=external-dns
```

Show the records created.

```bash
az network private-dns record-set a list -g $RG -z $AZURE_DNS_ZONE -o yaml

# SAMPLE OUTPUT
- aRecords:
  - ipv4Address: 10.2.0.7
  etag: 1f85f096-4036-408f-aa54-2d58d0523a96
  fqdn: hello.griffdemo123.com.
  id: /subscriptions/XXXXXX-XXXX/resourceGroups/ephexternaldnsdemo/providers/Microsoft.Network/privateDnsZones/griffdemo123.com/A/hello
  isAutoRegistered: false
  name: hello
  resourceGroup: ephexternaldnsdemo
  ttl: 300
  type: Microsoft.Network/privateDnsZones/A
- aRecords:
  - ipv4Address: 10.0.11.167
  etag: bf268fab-6678-4ae4-ae50-0cf49b314a0c
  fqdn: hello-clusterip.griffdemo123.com.
  id: /subscriptions/XXXXXX-XXXX/resourceGroups/ephexternaldnsdemo/providers/Microsoft.Network/privateDnsZones/griffdemo123.com/A/hello-clusterip
  isAutoRegistered: false
  name: hello-clusterip
  resourceGroup: ephexternaldnsdemo
  ttl: 300
  type: Microsoft.Network/privateDnsZones/A
```

### Create a Record for a Pod IP

If you need to create a DNS record for a pod IP, you can do this by creating a headless service that is annotated for external-dns. External DNS will see the service and then go and retrieve the pod IP, as documented in this PR: 
[for headless services use podip instead of hostip #498](https://github.com/kubernetes-sigs/external-dns/pull/498)

```bash
# Test ExternalDNS
cat << EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx
spec:
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - image: nginx
        name: nginx
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-svc
  annotations:
    external-dns.alpha.kubernetes.io/hostname: pod.griffdemo123.com
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: 80
  selector:
    app: nginx
  clusterIP: None
EOF
```

Check the record was created via CLI, or you can use the portal

```bash
# Get the pod IP from kubernetes
kubectl get pod -l app=nginx -o jsonpath='{.items[0].status.podIP}'

# Sample Output
10.244.2.14

# Get the IP from the Azure Private Zone
az network private-dns record-set a list -g $RG -z $AZURE_DNS_ZONE -o yaml --query "[?fqdn == 'pod.$AZURE_DNS_ZONE.'].aRecords"

# Sample Output
- - ipv4Address: 10.244.2.14
```

## Conclusion

In the above example we set up and AKS cluster, enabled with Azure Workload Identity and installed external-dns to automatically managed private DNS records in and Azure Private Zone. We demonstrated this for both Services and Pods. There are other options for managing the rights of the external-dns user, but I believe that Workload Identity gives you the best overall granularity of control.
