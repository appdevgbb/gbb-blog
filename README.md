# gbb-blog


## Local Dev with Remote theme

https://olivier3lanc.github.io/Jekyll-LibDoc/libdoc-install.html#local-with-remote-theme

Local with remote theme
[View example repository](https://github.com/olivier3lanc/LibDoc-remote-demo/tree/local)

It is possible to only write your content without complete LibDoc installation, just use LibDoc as remote theme. You only need to use locally [Jekyll remote theme plugin](https://github.com/benbalter/jekyll-remote-theme)

Install Jekyll on your machine following the steps described [here](https://jekyllrb.com/docs/)
Add a Gemfile with the following line
gem "jekyll-remote-theme"
and run bundle install to install the plugin

Add the following to your LibDoc’s local config file _config-local.yml

remote_theme: olivier3lanc/Jekyll-LibDoc
plugins:
    - jekyll-remote-theme
Run jekyll locally with a custom config file 

```:bash
cd docs
jekyll serve -c _config-local.yml
```
Feel free to use the [example repository](https://github.com/olivier3lanc/LibDoc-remote-demo/tree/local) as starter template.

## Adding additional syntax components with Prism

The remote template (LibDoc) is not always up to date. When new programming/scripting languages are available for syntax highlighting we'll likely need to manually add them to our Jekyll site.  visit the [prismJS GH repo](https://github.com/PrismJS/prism/tree/master/components) to search for and add the component ```prism-<language>.min.js file``` and then copy raw file and save to ```docs/assets/libdoc/js/prism/prism-<language>.min.js```

## Adding additional Authors

Author metadata is saved to a static file at ```docs/_data/authors.yaml```.  To add a new author simply append a new author in the following format:

```yaml
ray_kao:
  name: Ray Kao
  email: ray.kao@microsoft.com
  twitter: raykao
  github: raykao
  bio: Ray Kao is a Principal Cloud Architect at Microsoft, on the Digital and App Innovation, Azure Global Black Belt Team.
  image: https://github.com/raykao.png
```

The new author can now be added to the frontmater of a post or other site markdown file.  Below is an example of frontmatter to place at the beginning of each markdown file:

```markdown
---
title: Accessing Azure SQL DB via Workload Identity and Managed Identity
description: How to create an AKS cluster enabled with Workload Identity to access Azure SQL DB with Azure Managed Identity from a Kubernetes pod
authors: 
  - steve_griffith
---
```

This is essentially yaml array/list syntax so you can keep adding additional authors accordingly.  The author name matches up with the key/property name of the author in the data file.