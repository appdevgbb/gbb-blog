---
title: GitHub Actions Self Hosted Runners
description: Distilling key information about running GitHub Actions self hosted runners
authors: 
  - ray_kao
---

## Key Considerations for GitHub Actions

### GitHub App's Identity

When setting up GitHub Actions with a self-hosted runner, it's important to understand the key components of the GitHub App's identity:

- **Installation ID**: This is a unique identifier for the installation of the GitHub App on a specific repository or organization. It is used to authenticate API requests and to identify the context in which the app is operating.

- **App ID**: The App ID is a unique identifier for the GitHub App itself. It is assigned when the app is created and is used to identify the app in API requests and configuration settings.

- **Secret**: The secret is a private key used to sign JSON Web Tokens (JWTs) for authenticating API requests. It should be kept secure and not shared publicly. The secret is essential for ensuring that the communication between the GitHub App and GitHub's servers is secure.

Understanding these components is crucial for configuring and managing GitHub Actions with self-hosted runners effectively. Proper handling of these identifiers and secrets ensures secure and efficient operation of your CI/CD pipelines.

### Monitoring the GitHub Action Queue

To efficiently manage self-hosted runners, it's essential to monitor the GitHub Action Queue to determine if there is work that needs to be run. This can be achieved by using the GitHub REST API to check the status of the queue. 

You will need a service that can monitor this queue, such as KEDA (Kubernetes-based Event Driven Autoscaling). Additionally, you will need a secondary service that can scale your runners up or down based on the queue's status, which KEDA can also handle in conjunction with the native Kubernetes Pod Autoscaler in a Kuberenetes cluster.

Here is a workflow diagram that illustrates this process:

```mermaid
graph TD
  A[GitHub Actions Queue] -->|Monitor via REST API| B[Monitoring Service (e.g., KEDA)]
  B -->|Queue Status| C[Scaling Service (e.g., KEDA)]
  C -->|Scale Up/Down| D[Self-Hosted Runners]
```

1. **GitHub Actions Queue**: The queue where jobs are waiting to be processed by self-hosted runners.
2. **Monitoring Service**: A service like KEDA that monitors the queue via the GitHub REST API.
3. **Scaling Service**: A service that scales the number of self-hosted runners up or down based on the queue's status.
4. **Self-Hosted Runners**: The runners that execute the jobs from the GitHub Actions Queue.

By implementing this workflow, you can ensure that your self-hosted runners are efficiently managed and scaled according to the workload, optimizing resource usage and reducing costs.

### Storing the GitHub App's Private Key

When storing the GitHub App's private key, which is a PKCS PEM file, in Azure Key Vault, special care must be taken to ensure that the line endings are correctly encoded. Incorrect line endings can cause application errors for the action runner.

#### Using the Azure Portal

When using the Azure web portal to store the PEM file, there is a risk that the line endings may be mis-encoded. This can lead to issues when the key is retrieved and used by the GitHub Actions runner.

#### Using the Azure CLI

To avoid these issues, it is often easier and more reliable to store the PEM file using the Azure CLI. The CLI handles the line endings correctly, ensuring that the PEM file is stored and retrieved without encoding issues.

Here is an example of how to store the PEM file using the Azure CLI:

```sh
az keyvault secret set --vault-name <YourKeyVaultName> --name <YourSecretName> --file <PathToYourPEMFile>
```

By using the Azure CLI, you can ensure that the PEM file is stored with the correct line endings, preventing application errors and ensuring smooth operation of your GitHub Actions self-hosted runners.

### Obtaining the GitHub App's Application ID

To obtain the GitHub App's Application ID, follow these steps:

1. **Navigate to GitHub Settings**: Go to your GitHub account or organization settings where the GitHub App is installed.

2. **Select Developer Settings**: In the settings menu, select "Developer settings" to access the GitHub Apps configuration.

3. **Choose Your GitHub App**: Under "GitHub Apps", find and select the GitHub App for which you need the Application ID.

4. **View App Details**: In the app's settings page, you will find the "App ID" listed under the "About" section. This is the unique identifier for your GitHub App.

By following these steps, you can easily locate the Application ID required for configuring and managing your GitHub Actions with self-hosted runners.