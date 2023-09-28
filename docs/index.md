---
layout: libdoc/page
---

# Welcome

Welcome to the Azure Global Black Belts website.

<ul>
  {% for post in site.posts %}
    <li>
      <a href="{{ post.url }}">{{ post.title }}</a>
    </li>
  {% endfor %}
</ul>