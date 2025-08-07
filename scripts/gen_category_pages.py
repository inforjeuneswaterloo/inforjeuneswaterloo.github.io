import os
import glob
import re
import yaml
from slugify import slugify

# --- Configuration
# Le dossier où les pages de catégorie seront créées
CATEGORY_DIR = 'categories'
# Le layout Liquid à utiliser pour les pages d'archives
LAYOUT = 'category_archive'

def get_categories_from_posts():
    """Parcourt les posts pour trouver toutes les catégories uniques."""
    all_categories = set()
    post_files = glob.glob('_posts/*.md')
    
    for filename in post_files:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            front_matter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
            if front_matter_match:
                try:
                    front_matter = yaml.safe_load(front_matter_match.group(1))
                    if 'categories' in front_matter and isinstance(front_matter['categories'], list):
                        for category in front_matter['categories']:
                            all_categories.add(category)
                except yaml.YAMLError as e:
                    print(f"Erreur de syntaxe YAML dans le front matter de {filename}: {e}")
    return list(all_categories)

def create_category_page(category_name):
    """Crée le fichier Markdown pour une catégorie."""
    category_slug = slugify(category_name)
    file_path = os.path.join(CATEGORY_DIR, f'{category_slug}.md')
    
    front_matter_content = f"""---
layout: {LAYOUT}
title: Articles de la catégorie {category_name}
permalink: /categories/{category_slug}/
category: {category_name}
---
Cette page liste tous les articles de la catégorie.
<br><br>
"""
    
    # Ajoute la boucle Liquid directement dans le contenu du fichier
    liquid_content = """
{% for post in site.posts %}
  {% if post.categories contains page.category %}
    <h3><a href="{{ post.url }}">{{ post.title }}</a></h3>
    <p>{{ post.excerpt }}</p>
  {% endif %}
{% endfor %}
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(front_matter_content.strip())
        f.write(liquid_content)

def main():
    """Fonction principale pour exécuter le script."""
    os.makedirs(CATEGORY_DIR, exist_ok=True)
    
    categories = get_categories_from_posts()
    
    if not categories:
        print("Aucune catégorie trouvée dans les posts.")
        return
        
    print(f"Catégories trouvées : {categories}")
    for category in categories:
        create_category_page(category)
    
    print(f"{len(categories)} pages de catégorie créées dans le dossier '{CATEGORY_DIR}'.")

if __name__ == "__main__":
    main()