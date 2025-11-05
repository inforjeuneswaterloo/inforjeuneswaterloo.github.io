import requests
import json
import os
from pprint import pprint

# --- Configuration (Lue depuis GitHub Actions Secrets/ENV) ---
# Lisez ces variables depuis le workflow YAML
USERNAME = os.environ.get("BLUESKY_USERNAME")
PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD") 
BLUESKY_DID = os.environ.get("BSKY_DID_PLC") 

# Endpoints
API_PDS = "https://bsky.social"
AUTH_URL = f"{API_PDS}/xrpc/com.atproto.server.createSession"
FEED_URL = f"{API_PDS}/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_DID}&limit=10"

# Dossier de destination
DATA_DIR = "_data"
OUTPUT_FILE = os.path.join(DATA_DIR, "bluesky_posts.json")
# -----------------------------------------------------------

def get_post_image_url(post):
    """
    Tente d'extraire l'URL de la vignette d'un post Bluesky.
    Gère les images intégrées, les médias avec citation, et les liens externes.
    """
    embed = post.get('embed')
    if not embed:
        return None

    embed_type = embed.get('$type')

    # Cas A : Post avec des images intégrées
    if embed_type == 'app.bsky.embed.images':
        images = embed.get('images')
        if images and len(images) > 0:
            return images[0].get('thumb') 

    # Cas B : Post avec un média (image) et une citation
    elif embed_type == 'app.bsky.embed.recordWithMedia':
        media = embed.get('media')
        if media and media.get('$type') == 'app.bsky.embed.images':
            images = media.get('images')
            if images and len(images) > 0:
                return images[0].get('thumb')
    
    # Cas C : Post avec un lien externe (carte d'aperçu)
    elif embed_type == 'app.bsky.embed.external':
        external = embed.get('external')
        if external and external.get('thumb'):
            return external.get('thumb')
            
    return None

def fetch_bluesky_feed():
    """Authentifie l'utilisateur, récupère le flux, filtre les posts et sauvegarde les données."""
    
    # Vérification des variables d'environnement
    if not all([USERNAME, PASSWORD, BLUESKY_DID]):
        print("❌ Erreur de configuration : Un ou plusieurs identifiants Bluesky (USERNAME, PASSWORD, ou DID) sont manquants.")
        print(f"DEBUG: USERNAME={USERNAME}, PASSWORD={'***' if PASSWORD else 'None'}, DID={BLUESKY_DID}")
        return

    session = requests.Session()
    
    # 1. Authentification pour obtenir le token
    print(f"Tentative d'authentification pour {USERNAME}...")
    auth_payload = {
        "identifier": USERNAME,
        "password": PASSWORD
    }
    
    try:
        auth_response = session.post(AUTH_URL, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        
        access_jwt = auth_data.get('accessJwt')
        if not access_jwt:
            print("❌ Authentification échouée : Token JWT non trouvé.")
            return

        # 2. Préparation de la requête de flux avec le token
        headers = {
            "Authorization": f"Bearer {access_jwt}"
        }
        
        print(f"✅ Authentification réussie. Récupération du flux pour DID: {BLUESKY_DID}...")
        
        # 3. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        # 4. Extraction, filtrage et sauvegarde des items
        all_posts = []

        for item in data.get('feed', []):
            post = item.get('post')
            
            # 🛑 FILTRAGE : Exclure les Reposts (reason) et les Réponses (reply)
            
            # Vérification 1 : Filtrer les Reposts (Partage d'un autre utilisateur)
            if item.get('reason'):
                continue 
            
            # Vérification 2 : Filtrer les Réponses/Threads
            if post and post.get('record', {}).get('reply'):
                continue 

            # Si le post a passé les filtres, on le traite
            if post:
                # Ajout de l'URL de l'image simplifiée au niveau racine
                post['image_url'] = get_post_image_url(post)
                all_posts.append(post)

        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({'posts': all_posts}, f, ensure_ascii=False, indent=2)

        print(f"✅ Succès : {len(all_posts)} posts sauvegardés dans {OUTPUT_FILE}")

    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification ou du flux : {e}")
        try:
            print("Réponse d'erreur du serveur :")
            pprint(e.response.json())
        except:
            pass
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

if __name__ == "__main__":
    fetch_bluesky_feed()