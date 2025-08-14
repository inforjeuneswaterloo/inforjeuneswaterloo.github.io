import feedparser
import json
import yaml
import os
import re
from datetime import datetime, timedelta, timezone

# L'URL du flux RSS de Mastodon que vous souhaitez récupérer
RSS_FEED_URL = "https://mastodon.social/@job4student.rss"

# Le nom du fichier de sortie
OUTPUT_FILE = "_data/job4u.json"

def get_mastodon_feed():
    """
    Récupère le flux RSS de Mastodon et retourne une liste de messages.
    """
    feed = feedparser.parse(RSS_FEED_URL)
    messages = []
    
    # Définit une variable pour la date d'aujourd'hui et une autre pour la date il y a 7 jours
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7) # <-- Correction ici
    
    for entry in feed.entries:
        # Vérifie si le post a été publié dans les 7 derniers jours
        # La date du flux est une date avec fuseau horaire, nous devons donc en faire une aussi.
        published_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
        
        if published_date > seven_days_ago: # <-- La comparaison fonctionne maintenant
            # Extrait l'ID du toot
            toot_id = re.search(r'(\d+)$', entry.link).group(1) if re.search(r'(\d+)$', entry.link) else None
            
            # Génère l'URL d'intégration pour le toot
            embed_url = f'https://mastodon.social/@job4student/{toot_id}/embed' if toot_id else None
            
            # Extrait le contenu du message
            message_content = entry.summary if entry.summary else ""
            
            # Génère un titre à partir du contenu si un titre n'est pas disponible
            message_title = entry.title if hasattr(entry, 'title') else message_content.split('</p>')[0].replace('<p>', '').strip() if '<p>' in message_content else message_content.strip()

            message = {
                "title": message_title,
                "link": entry.link,
                "published": entry.published,
                "content": message_content,
                "toot_id": toot_id,
                "embed_url": embed_url,
            }
            messages.append(message)
    return messages

def save_feed_to_file(data):
    """
    Sauvegarde le flux dans un fichier JSON ou YAML.
    """
    if OUTPUT_FILE.endswith(".json"):
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"Le flux a été sauvegardé dans le fichier {OUTPUT_FILE}")
    
    elif OUTPUT_FILE.endswith(".yaml") or OUTPUT_FILE.endswith(".yml"):
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
        print(f"Le flux a été sauvegardé dans le fichier {OUTPUT_FILE}")

if __name__ == "__main__":
    messages = get_mastodon_feed()
    save_feed_to_file(messages)