---
layout: category_archive
title: Articles de la catégorie Téléchargements
permalink: /categories/telechargements/
category: Téléchargements
---
Cette page liste tous les articles de la catégorie.
<br><br>
{% for post in site.posts %}
  {% if post.categories contains page.category %}
    <h3><a href="{{ post.url }}">{{ post.title }}</a></h3>
    <p>{{ post.excerpt }}</p>
  {% endif %}
{% endfor %}
