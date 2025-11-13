import requests
import json
import os
import pytz
import re

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
# Assurez-vous que ces variables sont bien définies dans votre environnement d'exécution (ex: GitHub Secrets)
USERNAME = os.environ.get("BLUESKY_USERNAME")
PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD") 
BLUESKY_DID = os.environ.get("BSKY_DID_PLC") # Utilisé comme identifiant de l'auteur

# Configuration du fichier de sortie et du filtre
DATA_DIR = "_data"
TARGET_TAG = "yotm" # <--- TAG CIBLE
# Fichier 1 : Le fichier filtré (nom basé sur le tag)
OUTPUT_FILTERED_FILE = os.path.join(DATA_DIR, f"bluesky_{TARGET_TAG}_posts.json") 
# NOUVEAU FICHIER 2 : Le fichier de toutes les données
OUTPUT_ALL_FILE = os.path.join(DATA_DIR, "bluesky_posts.json")
TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

# URL de l'API et du Flux (définition globale)
API_PDS = "https://bsky.social"
FEED_LIMIT = 100 
FEED_URL = f"{API_PDS}/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_DID}&limit={FEED_LIMIT}"

# Regex pour identifier les URLs
URL_REGEX = r"https?://[^\s]+|www\.[^\s]+" 

# --- Fonctions Utilitaires ---

def clean_data_directory(directory):
    """Crée le répertoire _data s'il n'existe pas."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_post_image_url(post):
    """Tente d'extraire l'URL de la vignette d'un post Bluesky."""
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
    elif embed_type == 'app.bsky.embed.external#view' or embed_type == 'app.bsky.embed.external':
        external = embed.get('external')
        if external and external.get('thumb'):
            return external.get('thumb')
            
    return None

def post_has_tag(post, target_tag):
    """
    Vérifie si un post Bluesky contient le hashtag cible en utilisant les 'facets'.
    C'est la méthode la plus fiable pour identifier les tags.
    """
    facets = post.get('record', {}).get('facets')
    if not facets:
        return False
        
    normalized_target_tag = target_tag.lower().lstrip('#')

    for facet in facets:
        for feature in facet.get('features', []):
            if feature.get('$type') == 'app.bsky.richtext.facet#tag':
                tag = feature.get('tag')
                if tag and tag.lower() == normalized_target_tag:
                    return True
    return False


def save_data_to_json(data_list, output_path):
    """Sauvegarde la liste des posts dans le fichier JSON spécifié."""
    clean_data_directory(DATA_DIR)
    
    try:
        # Note : On sauvegarde la liste sous la clé 'posts' pour faciliter l'accès Jekyll (site.data.fichier.posts)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        
        print(f"✅ Succès : {len(data_list)} posts sauvegardés dans {output_path}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture du fichier JSON '{output_path}': {e}")
        return False

# --- Fonction Principale ---
def fetch_bluesky_feed():
    """Authentifie, récupère le flux, filtre par tag et sauvegarde les deux fichiers."""
    
    # Vérification des variables d'environnement
    if not all([USERNAME, PASSWORD, BLUESKY_DID]):
        print("❌ Erreur de configuration : Un ou plusieurs identifiants Bluesky sont manquants.")
        return

    session = requests.Session()
    auth_url = f"{API_PDS}/xrpc/com.atproto.server.createSession"
    auth_payload = {"identifier": USERNAME, "password": PASSWORD}
    
    try:
        # 1. Authentification
        auth_response = session.post(auth_url, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        access_jwt = auth_data.get('accessJwt')
        headers = {"Authorization": f"Bearer {access_jwt}"}
        
        print(f"✅ Authentification réussie. Récupération du flux (limite: {FEED_LIMIT})...")
        
        # 2. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        all_feed_items = data.get('feed', [])
        
        # --- Sauvegarde du Fichier 1 : TOUTES les données brutes ---
        # On extrait seulement le 'post' de chaque 'item' pour simplifier le JSON de sortie
        all_posts_data = [item.get('post') for item in all_feed_items if item.get('post')]
        save_data_to_json(all_posts_data, OUTPUT_ALL_FILE)


        # --- Traitement pour le Fichier 2 : Données filtrées ---
        yotm_posts = [] 

        for item in all_feed_items:
            post = item.get('post')
            
            # FILTRAGE 1 : Exclure les Reposts et les Réponses
            if item.get('reason') or (post and post.get('record', {}).get('reply')):
                continue 
            
            if post:
                # FILTRAGE 2 : Vérification du Tag Cible
                if not post_has_tag(post, TARGET_TAG):
                    continue # Passe au post suivant si le tag est absent

                # --- Traitement des posts VALIDES ET FILTRÉS ---
                
                # Nettoyage du texte (suppression des URLs)
                post_text = post['record']['text']
                cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                post['record']['text'] = cleaned_text 

                # Ajout de l'URL de l'image simplifiée
                post['image_url'] = get_post_image_url(post)
                
                # Ajout à la liste finale (yotm_posts)
                yotm_posts.append(post)

        # 4. Sauvegarde finale du Fichier 2 : Le flux filtré
        save_data_to_json(yotm_posts, OUTPUT_FILTERED_FILE)

    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification ou du flux : {e}")
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

# --- Point d'Entrée ---
if __name__ == "__main__":
    fetch_bluesky_feed()