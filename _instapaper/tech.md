---
layout: page-single
title: Technologie
collection: instapaper
data-file: instapaper_tech
permalink: /instapaper/tech/
color: 973b90
button:
  text: Lire l'article
  icon: square-arrow-out-up-right
---
{% assign file = page['data-file'] %}
{% assign items = site.data[file] %}
{% assign color = page.color %}
{% assign button=page.button %}
{% include instapaper.html items=items button=button color=color %}
