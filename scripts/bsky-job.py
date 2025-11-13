import requests
import json
import os
import pytz
import re
from datetime import datetime, timedelta 

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
USERNAME = os.environ.get("BLUESKY_JOB_USERNAME") 
PASSWORD = os.environ.get("BLUESKY_JOB_PASSWORD") 
BLUESKY_DID = os.environ.get("BLUESKY_JOB_DID_PLC") 

# Configuration du fichier de sortie et du filtre
DATA_DIR = "_data"
TARGET_TAG = "ij1410" 
# Fichier 1 : Tous les posts (sans filtrage, pour l'audit)
OUTPUT_ALL_FILE = os.path.join(DATA_DIR, "bluesky_job_posts.json") 
# Fichier 2 : Posts filtrés par tag et date (pour l'affichage)
OUTPUT_FILTERED_FILE = os.path.join(DATA_DIR, "bluesky_job_waterloo_posts.json") 
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
    """Tente d'extraire l'URL de la vignette d'un post Bluesky. 
    Ignore les vignettes d'articles partagés (embed.external)."""
    embed = post.get('embed')
    if not embed:
        return None

    embed_type = embed.get('$type')

    # Cas A : Images intégrées
    if embed_type == 'app.bsky.embed.images':
        images = embed.get('images')
        if images and len(images) > 0:
            return images[0].get('thumb') 

    # Cas B : Média avec citation (si le média est une image)
    elif embed_type == 'app.bsky.embed.recordWithMedia':
        media = embed.get('media')
        if media and media.get('$type') == 'app.bsky.embed.images':
            images = media.get('images')
            if images and len(images) > 0:
                return images[0].get('thumb')
    
    # Cas C : Lien externe (articles partagés) -> Ignoré
    elif embed_type == 'app.bsky.embed.external#view' or embed_type == 'app.bsky.embed.external':
        return None 
            
    return None

def post_has_tag(post, target_tag):
    """
    Vérifie si un post Bluesky contient le hashtag cible en utilisant les 'facets'.
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

def get_external_link_uri(post_facets):
    """
    Récupère l'URI de destination du premier lien externe trouvé dans les facets.
    """
    if not post_facets:
        return None
        
    for facet in post_facets:
        for feature in facet.get('features', []):
            # Cible le type de feature qui représente un lien externe
            if feature.get('$type') == 'app.bsky.richtext.facet#link':
                # L'URI du lien est dans 'uri'
                return feature.get('uri') 
    return None


def save_data_to_json(data_list, output_path):
    """Sauvegarde la liste des posts dans le fichier JSON spécifié (régénération)."""
    clean_data_directory(DATA_DIR)
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        
        print(f"✅ Succès : {len(data_list)} posts sauvegardés dans {output_path}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture du fichier JSON '{output_path}': {e}")
        return False

# --- Fonction Principale ---
def fetch_bluesky_feed():
    """Authentifie, récupère le flux, filtre par tag/date et sauvegarde les deux fichiers."""
    
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
        
        # Détermination de la borne temporelle (7 jours en UTC)
        now_utc = datetime.now(pytz.utc)
        seven_days_ago_utc = now_utc - timedelta(days=7)
        
        print(f"✅ Authentification réussie. Récupération du flux (limite: {FEED_LIMIT})...")

        # 2. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        # 3. Sauvegarde immédiate du fichier "ALL POSTS"
        all_feed_items = data.get('feed', [])
        all_posts_data = [item.get('post') for item in all_feed_items if item.get('post')]
        save_data_to_json(all_posts_data, OUTPUT_ALL_FILE)
        
        # 4. Traitement et filtrage pour le fichier "WATERLOO POSTS"
        filtered_posts = [] 

        for item in all_feed_items:
            post = item.get('post')
            
            if not post:
                continue

            post_record = post.get('record', {})

            # --- AJOUT CRUCIAL 1 : Extraction et ajout de l'URI/Permalink ---
            post_uri = post.get('uri')
            if post_uri:
                post['uri'] = post_uri
                post['permalink'] = post_uri.replace(
                    "at://", "https://bsky.app/profile/"
                ).replace(
                    "/app.bsky.feed.post/", "/post/"
                )
            # --------------------------------------------------------------------------
            
            # --- AJOUT CRUCIAL 2 : Extraction et ajout des FACETS ---
            post_facets = post_record.get('facets')
            if post_facets:
                post['facets'] = post_facets
            # ----------------------------------------------------------------------
            
            # --- AJOUT CRUCIAL 3 : Extraction de l'URI d'un Lien Externe dans Facet ---
            external_uri = get_external_link_uri(post_facets)
            if external_uri:
                post['external_link_uri'] = external_uri
            # --------------------------------------------------------------------------

            # FILTRAGE 0 : Bornage temporel (moins de 7 jours)
            created_at_str = post_record.get('createdAt')
            if created_at_str:
                try:
                    # Conversion de l'horodatage en datetime conscient du fuseau horaire (UTC)
                    created_at_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')).astimezone(pytz.utc)
                    
                    if created_at_dt < seven_days_ago_utc:
                        continue # Skip si trop ancien
                except ValueError:
                    continue # Skip si date invalide
            
            # FILTRAGE 1 : Exclure les Reposts et les Réponses
            if item.get('reason') or post_record.get('reply'):
                continue 
            
            # FILTRAGE 2 : Vérification du Tag Cible (#bwaterloo)
            if not post_has_tag(post, TARGET_TAG):
                continue 

            # --- Traitement des posts VALIDES ET FILTRÉS ---
            
            # Nettoyage du texte (suppression des URLs)
            post_text = post_record.get('text', '')
            cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
            post_record['text'] = cleaned_text 

            # Extraction du titre (première ligne)
            post['title'] = cleaned_text.split('\n', 1)[0].strip()

            # Suppression de l'embed d'article externe (pour ne pas garder titre/vignette)
            embed_type = post.get('embed', {}).get('$type')
            if embed_type in ['app.bsky.embed.external#view', 'app.bsky.embed.external'] and 'embed' in post:
                del post['embed'] 

            # Ajout de l'URL de l'image simplifiée
            post['image_url'] = get_post_image_url(post)
            
            # Ajout à la liste finale 
            filtered_posts.append(post)

        # 5. Sauvegarde finale du flux filtré (régénération du fichier)
        save_data_to_json(filtered_posts, OUTPUT_FILTERED_FILE)

    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification ou du flux : {e}")
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

# --- Point d'Entrée ---
if __name__ == "__main__":
    fetch_bluesky_feed()