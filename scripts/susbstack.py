import feedparser
import re
import os
import json

# Configuration spécifique à Substack
SUBSTACK_RSS_URL = "https://ijwaterloo.substack.com/feed"
DATA_DIR = "_data"
OUTPUT_SUBSTACK_FILE = os.path.join(DATA_DIR, "substack_veille_presse.json")

def save_data_to_json(data_list, output_path):
    """Fonction de sauvegarde (réutilisant ta logique existante)"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2)
        print(f"✅ Succès : {len(data_list)} articles Substack sauvegardés.")
    except IOError as e:
        print(f"❌ Erreur d'écriture : {e}")

def fetch_substack_feed():
    """Récupère et nettoie les 5 derniers articles de la veille Substack"""
    print(f"📡 Analyse du flux RSS : {SUBSTACK_RSS_URL}")
    
    try:
        feed = feedparser.parse(SUBSTACK_RSS_URL)
        if not feed.entries:
            print("⚠️ Aucun article trouvé sur Substack.")
            return

        substack_posts = []
        for entry in feed.entries[:5]:
            # Nettoyage des balises HTML dans le résumé
            summary_clean = re.sub(r'<[^>]+>', '', entry.summary).strip()
            
            substack_posts.append({
                'title': entry.title,
                'url': entry.link,
                'published': entry.published,
                # On limite le résumé à 180 caractères pour l'affichage Jekyll
                'summary': (summary_clean[:180] + "...") if len(summary_clean) > 180 else summary_clean
            })
        
        save_data_to_json(substack_posts, OUTPUT_SUBSTACK_FILE)

    except Exception as e:
        print(f"❌ Erreur lors de l'extraction Substack : {e}")

if __name__ == "__main__":
    fetch_substack_feed()