---
authors:
- diego_casati
date: '2025-11-27'
description: Tools of the Trade is a series where members of the GBB team share the tools and workflows that help us work effectively with Kubernetes.
tags:
- kubernetes
- aks
- productivity
title: "Tools of the Trade: Working with Multiple Clusters"
---

# Tools of the Trade: Working with Multiple Clusters

Welcome to "Tools of the Trade" - a series where we share the tools and workflows that help us work more effectively. In this first post, I'll show you how I manage multiple AKS clusters without losing track of which cluster I'm working on. If you've ever accidentally deployed to the wrong cluster, this one's for you.

<!-- truncate -->

### The problem statement

How can I keep track of all of the AKS clusters that I have to deal with on a weekly basis, making sure that I'm actually working in the right cluster? 

### My approach

I routinely run tests for customers that involve the creation of new AKS clusters so I can understand and test complex scenarios. Since in many cases these are temporary in nature, I have established a workflow (aka "It works on my machine") that I tend to follow. To start, I create a directory for all of my clusters. In it, I add a `.envrc` file that contains environment variables that are scoped to the cluster that I'm working on _and_ I use a tool called `direnv` to hook into bash and autoload/unload the variables exposed by `.envrc`:

1. Create a placeholder directory for your cluster:

```bash
mkdir ~/clusters/ && cd ~/clusters/
```

2. Install `direnv`

```bash
sudo apt install direnv
```

3. Add the hook to bash by adding this to `~/.bashrc`

```bash
_direnv_hook() {
  local previous_exit_status=$?;
  trap -- '' SIGINT;
  eval "$("/usr/bin/direnv" export bash)";
  trap - SIGINT;
  return $previous_exit_status;
};
if ! [[ "${PROMPT_COMMAND:-}" =~ _direnv_hook ]]; then
  PROMPT_COMMAND="_direnv_hook${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi
```

4. Reload your `bashrc`

```bash
source ~/.bashrc
```

Great, we are ready now. With that in place, when I `cd` into that directory, I know that I will be working with a `KUBECONFIG` that is related to a specific cluster. 

:::note
Whenever you make changes to your `.envrc` file, you will need to run `direnv allow` again to approve the updated content.
:::

:::tip
Another approach is to use single `KUBECONFIG` file and then use [kubectx](https://github.com/ahmetb/kubectx) to choose the cluster you will be working on. Use the tool that is the most convenient to you, own it, have fun!
:::

### Trying this out

Let's try an example. Suppose we need to create two AKS clusters, one called `aks-alpha` and another one called `aks-bravo`.

Start by creating the directories for each cluster inside of your `~/clusters` directory:

```bash
mkdir -p {aks-alpha,aks-bravo}
```

You should now have these two directories:

```bash
drwxr-xr-x  2 dcasati dcasati 4.0K Nov 27 10:22 aks-bravo
drwxr-xr-x  2 dcasati dcasati 4.0K Nov 27 10:22 aks-alpha
```

For the **alpha** cluster, declare the following environment variables for a hypothetical AKS cluster:

```bash
cat <<EOF> aks-alpha/.envrc
# Environment variables
export AKS_CLUSTER_NAME="aks-alpha"
export RESOURCE_GROUP="rg-aks-alpha"
export LOCATION="westus3"
export KUBECONFIG=${PWD}/cluster.config
EOF
```

Change directories to the `aks-alpha` cluster. When `direnv` asks for your permission, allow it

```bash
cd aks-alpha/
direnv: error /home/dcasati/clusters/aks-alpha/.envrc is blocked. Run `direnv allow` to approve its content
```

Type `direnv allow`

Expect:

```bash
$ direnv allow
direnv: loading ~/clusters/aks-alpha/.envrc
direnv: export +AKS_CLUSTER_NAME +KUBECONFIG +LOCATION +RESOURCE_GROUP
```

You can see that the environment variables declared inside of the `.envrc` were automatically loaded. A quick test here is to see the `$AKS_CLUSTER_NAME` - we will do the same for the **bravo** cluster too:

```bash
$ echo $AKS_CLUSTER_NAME 
aks-alpha
```

Now if you go out of this directory, these variables will be automatically unloaded by `direnv`

```bash
cd ..
direnv: unloading
```

Create the same `.envrc` but for the **bravo** cluster:

```bash
cat <<EOF> aks-bravo/.envrc
# Environment variables
export AKS_CLUSTER_NAME="aks-bravo"
export RESOURCE_GROUP="rg-aks-bravo"
export LOCATION="westus3"
export KUBECONFIG=${PWD}/cluster.config
EOF
```

Now `cd` into the `aks-bravo` directory and allow `direnv`:

```bash
cd aks-bravo/
direnv allow
```

Verify the new variables are in place:

```bash
$ echo $AKS_CLUSTER_NAME 
aks-bravo
```

### Demo

<iframe 
  src="https://asciinema.org/a/qSay000TvIwzS5duV7wYAI2nU/iframe" 
  width="100%" 
  height="400"
  style={{border: 'none'}}
></iframe>

### Bonus: Visual confirmation with PS1

This is a tip that I added to the Platform Engineering lab [Build a GitOps-Driven Platform on AKS with the App of Apps Pattern](https://azure-samples.github.io/aks-labs/docs/platform-engineering/app-of-apps) - if you haven't checked that lab, you should, there's some cool stuff there.

Since you might be switching between clusters throughout your day, it's easy to lose track of which cluster you're currently working with. The approach I use in my day-to-day is to add your current Kubernetes context to your bash `PS1` variable.

Do this, add this to the bottom of your `~/.bashrc` file:

```bash
# Add kubectl current context to prompt
export PS1='\[\033[01;34m\]\w\[\033[00m\] \[\033[01;36m\][$(kubectl config current-context 2>/dev/null || echo "no-cluster")]\[\033[00m\]\n\$ '
```

Then reload your shell:

```bash
source ~/.bashrc
```

Your prompt will now display the current cluster name, like this:

```
~/clusters/aks-bravo [aks-bravo]
$
```

### Conclusion

In this post, we explored how to use `direnv` to manage environment variables scoped to specific clusters and how to customize your bash prompt to always show which cluster you're working with. This simple workflow has saved me countless times from accidentally running commands against the wrong cluster. Give it a try and let me know how it works for you!