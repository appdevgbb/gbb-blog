---
authors:
- diego_casati
date: '2026-02-13'
description: Tools of the Trade is a series where members of the GBB team share the tools and workflows that help us work effectively with Kubernetes.
tags:
- kubernetes
- terminal
- productivity
title: "Tools of the Trade: Adding fuzziness to the mix"
---

# Tools of the Trade: Adding fuzziness to the mix

In this Tool of the Trade, we take a quick look at how fuzziness with `fzf` can enhance your day-to-day life in the terminal. This is one of those tools that you did not know you really needed until you try it.

<!-- truncate -->

For this article, we'll focus purely on adding fuzziness with the official [fzf shell integration](https://junegunn.github.io/fzf/shell-integration/) so you can jump between cluster directories, open files, and search shell history without bespoke scripts.

### Add fzf shell integration

To get the key bindings and completion from the official integration, install `fzf` and then enable the hooks:

Clone the repository locally:

```bash
git clone --depth 1 https://github.com/junegunn/fzf.git ~/.fzf
```

Run the installer to add key bindings and completion:

```bash
~/.fzf/install --key-bindings --completion --no-update-rc
```

Source the `fzf` bash helpers in your shell init:

```bash
echo 'source ~/.fzf.bash' >> ~/.bashrc
```

Add the `fzf` shell integration to your prompt environment:

```bash
cat <<'EOF' >> ~/.bashrc
# fzf
eval "$(fzf --bash)"
EOF
```

Reload your shell configuration:

```bash
source ~/.bashrc
```

With this enabled you get:
- `Ctrl+T` to fuzzy-find files and insert the result on the command line.
- `Alt+C` to fuzzy `cd` into directories (perfect for jumping between clusters).
- `Ctrl+R` to fuzzy-search shell history.

The 'Hello World' version of `fzf` should be just this one. Try navigating your shell  `history`:

<iframe 
  src="https://asciinema.org/a/CFt9xrPn59afduk7/iframe" 
  width="100%" 
  height="400"
  style={{border: 'none'}}
></iframe>

### Quick fuzzy helpers for clusters

You can combine the shell integration with a small helper to jump into a cluster directory under `~/clusters`:

```bash
clusters() {
  local target
  target=$(find "$HOME/clusters" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort | fzf --prompt="cluster dir> ") || return
  cd "$HOME/clusters/$target"
}
```

Run `clusters` and pick with `fzf`; if you kept the `direnv` workflow from the earlier post, your variables will load automatically when you land in the directory. If you prefer a single `KUBECONFIG`, you can swap `clusters` for a context switcher like this:

<iframe 
  src="https://asciinema.org/a/NPN43SKa3F6CEoPc/iframe" 
  width="100%" 
  height="400"
  style={{border: 'none'}}
></iframe>

And this is a DIY version of  Ahmed's famous `kubectx` command:

```bash
kctx() {
  local ctx
  ctx=$(kubectl config get-contexts -o name | fzf --prompt="k8s context> ") || return
  kubectl config use-context "$ctx"
}
```

<iframe 
  src="https://asciinema.org/a/N1yEqzemu5Xp5pvf/iframe" 
  width="100%" 
  height="400"
  style={{border: 'none'}}
></iframe>

### Change directories quickly

You can change directories quickly using `ALT+c`, check this out

<iframe 
  src="https://asciinema.org/a/aS3E0UXtJz9omrhV/iframe" 
  width="100%" 
  height="400"
  style={{border: 'none'}}
></iframe>

### Conclusion

In this post, we enabled `fzf` shell integration, added a couple of tiny helpers to jump between cluster directories or switch contexts, and tweaked `PS1` to always show the active Kubernetes context. Pair this with the directory-per-cluster workflow from the earlier article and you get fast, low-friction navigation across all your clusters.