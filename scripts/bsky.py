import requests
import json
import os
from pprint import pprint

# --- Configuration (À MODIFIER !) ---
# Utilisez les variables d'environnement si possible (recommandé pour la sécurité)
USERNAME = os.getenv("BLUESKY_USERNAME")  # Définir cette variable d'environnement avant d'exécuter le script 
PASSWORD = os.getenv("BLUESKY_APP_PASSWORD")  # Définir cette variable d'environnement avant d'exécuter le script
BLUESKY_DID = os.getenv("BSKY_DID_PLC")  # Définir cette variable d'environnement avant d'exécuter le script

# Endpoints
API_PDS = "https://bsky.social"
AUTH_URL = f"{API_PDS}/xrpc/com.atproto.server.createSession"
FEED_URL = f"{API_PDS}/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_DID}&limit=10"

# Dossier de destination
DATA_DIR = "_data"
OUTPUT_FILE = os.path.join(DATA_DIR, "bluesky_posts.json")
# -------------------------------------

def fetch_bluesky_feed():
    """Authentifie l'utilisateur, récupère le flux et sauvegarde les posts."""
    session = requests.Session()
    
    # 1. Authentification pour obtenir le token
    print("Tentative d'authentification...")
    auth_payload = {
        "identifier": USERNAME,
        "password": PASSWORD
    }
    
    try:
        auth_response = session.post(AUTH_URL, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        
        # Récupération du token d'accès
        access_jwt = auth_data.get('accessJwt')
        if not access_jwt:
            print("❌ Authentification échouée : Token JWT non trouvé.")
            return

        # 2. Préparation de la requête de flux avec le token
        headers = {
            "Authorization": f"Bearer {access_jwt}"
        }
        
        print("✅ Authentification réussie. Récupération du flux...")
        
        # 3. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        # 4. Extraction et sauvegarde des items
        posts = [item['post'] for item in data.get('feed', [])]

        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({'posts': posts}, f, ensure_ascii=False, indent=2)

        print(f"✅ Succès : {len(posts)} posts sauvegardés dans {OUTPUT_FILE}")

    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification ou du flux : {e}")
        # Affiche le contenu de l'erreur pour aider au débogage
        if 'response' in locals(): 
            try:
                pprint(e.response.json())
            except:
                print("Le serveur n'a pas retourné de JSON d'erreur.")
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

if __name__ == "__main__":
    fetch_bluesky_feed()