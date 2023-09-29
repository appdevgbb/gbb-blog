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
jekyll serve -c _config-local.yml
```
Feel free to use the [example repository](https://github.com/olivier3lanc/LibDoc-remote-demo/tree/local) as starter template.

## Adding additional 