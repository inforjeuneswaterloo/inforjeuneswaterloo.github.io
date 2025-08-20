---
layout: list
title: Quai d'embarquement
permalink: /yotm/welcome/
buttons:
  - btn:
    enabled: false
    class: 
    icon: 
    text:
    href: 
---
{% assign list=site.data.yotm.welcome-list %}
{% for item in list %}
  <li class="list-group-item d-flex justify-content-between align-items-center">
    <span><h6 class="display">{{ item.section.text }}</h6></span>
      {%if item.section.button %}
          <a class="btn btn-light text-decoration-none" href="{{item.section.button.link | relative_url}}">
              <i class="fa-solid fa-arrow-right"></i>
          </a>
      {%endif%}
  </li>
{% endfor %}
