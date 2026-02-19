---
layout: category-list
title: Articles de la catégorie International
permalink: /categories/international/
category: International
---
Cette page liste tous les articles de la catégorie.
<br><br>
{% for post in site.posts %}
  {% if post.categories contains page.category %}
    <h3><a href="{{ post.url }}">{{ post.title }}</a></h3>
    <p>{{ post.excerpt }}</p>
  {% endif %}
{% endfor %}
