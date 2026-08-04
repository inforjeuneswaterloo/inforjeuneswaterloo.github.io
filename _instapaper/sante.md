---
layout: page-single
title: Santé
collection: instapaper
data-file: instapaper_sante
permalink: /instapaper/sante/
color: 1db0a3
button:
  text: Lire l'article
  icon: square-arrow-out-up-right
---
{% assign file = page['data-file'] %}
{% assign items = site.data[file] %}
{% assign color = page.color %}
{% assign button=page.button %}
{% include instapaper.html items=items button=button color=color %}
