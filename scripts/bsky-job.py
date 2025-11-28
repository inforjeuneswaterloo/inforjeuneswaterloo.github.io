import requests
import json
import os
import pytz
import re
import datetime # ⬅️ Ajout de l'importation nécessaire pour la gestion des dates

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
USERNAME = os.environ.get("BLUESKY_JOB_USERNAME")
PASSWORD = os.environ.get("BLUESKY_JOB_PASSWORD") 
BLUESKY_DID = os.environ.get("BLUESKY_JOB_DID_PLC") 

# Configuration du fichier de sortie et du filtre
DATA_DIR = "_data"
TARGET_TAG = "ij410" 
OUTPUT_FILTERED_FILE = os.path.join(DATA_DIR, f"bluesky_{TARGET_TAG}_posts.json") 
OUTPUT_ALL_FILE = os.path.join(DATA_DIR, "bluesky_posts.json")
OUTPUT_PINNED_FILE = os.path.join(DATA_DIR, "bsky_posts_pinned.json") 
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

# 🚩 NOUVEAU : Fonction utilitaire pour la conversion et localisation des dates
def localize_bluesky_timestamp(timestamp_str, target_tz):
    """Convertit une chaîne de temps Bluesky (UTC) en objet datetime localisé."""
    try:
        # 1. Parse la chaîne en un objet datetime (naive), en ignorant les millisecondes après le point
        dt_utc_naive = datetime.datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        
        # 2. Rend l'objet conscient (aware) qu'il est en UTC
        dt_utc_aware = pytz.utc.localize(dt_utc_naive)
        
        # 3. Convertit l'heure UTC en l'heure cible
        dt_localized = dt_utc_aware.astimezone(target_tz)
        
        return dt_localized
    except Exception:
        return None

def get_post_image_url(post):
    """Tente d'extraire l'URL de la vignette d'un post Bluesky."""
    embed = post.get('embed')
    if not embed:
        return None
    embed_type = embed.get('$type')
    if embed_type == 'app.bsky.embed.images':
        images = embed.get('images')
        if images and len(images) > 0:
            return images[0].get('thumb') 
    elif embed_type == 'app.bsky.embed.recordWithMedia':
        media = embed.get('media')
        if media and media.get('$type') == 'app.bsky.embed.images':
            images = media.get('images')
            if images and len(images) > 0:
                return images[0].get('thumb')
    elif embed_type == 'app.bsky.embed.external#view' or embed_type == 'app.bsky.embed.external':
        external = embed.get('external')
        if external and external.get('thumb'):
            return external.get('thumb')
    return None

def post_has_tag(post, target_tag):
    """Vérifie si un post Bluesky contient le hashtag cible en utilisant les 'facets'."""
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
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        print(f"✅ Succès : {len(data_list)} posts sauvegardés dans {output_path}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture du fichier JSON '{output_path}': {e}")
        return False

def get_pinned_post_uri(session, did, headers):
    """Récupère l'URI (at://...) du post épinglé d'un utilisateur depuis son profil."""
    profile_url = f"{API_PDS}/xrpc/app.bsky.actor.getProfile?actor={did}"
    try:
        response = session.get(profile_url, headers=headers)
        response.raise_for_status()
        profile_data = response.json()
        return profile_data.get('pinnedPost') 
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur lors de la récupération du profil pour le post épinglé : {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur inattendue lors de la récupération du post épinglé : {e}")
        return None

# --- Fonction Principale ---
def fetch_bluesky_feed():
    """Authentifie, récupère le flux, filtre par tag et temps, recherche le post épinglé et sauvegarde les trois fichiers."""
    
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

        # 🚩 Bornage Temporel : Calcul de la date limite (-7 jours)
        time_limit_days = 7 # ⬅️ Borne fixée à 7 jours
        now_localized = datetime.datetime.now(TARGET_TIMEZONE)
        time_cutoff = now_localized - datetime.timedelta(days=time_limit_days)
        print(f"⏰ Bornage actif : Ne conserver que les posts postérieurs au {time_cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}.")

        # 2. Récupération de l'URI du post épinglé
        pinned_post_uri = get_pinned_post_uri(session, BLUESKY_DID, headers)
        if pinned_post_uri:
            print(f"✅ URI du post épinglé trouvé : {pinned_post_uri}")
        else:
            print("ℹ️ Aucun post épinglé trouvé ou erreur lors de la récupération.")
        
        # 3. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        all_feed_items = data.get('feed', [])
        
        # Préparation des listes de sortie
        pinned_posts = [] 
        
        # On extrait seulement le 'post' de chaque 'item' pour simplifier le JSON de sortie
        all_posts_data = [item.get('post') for item in all_feed_items if item.get('post')]
        # --- Sauvegarde du Fichier 1 : TOUTES les données brutes (sans filtrage) ---
        save_data_to_json(all_posts_data, OUTPUT_ALL_FILE)


        # --- Traitement pour le Fichier 2 (filtré par tag) et Fichier 3 (épinglé) ---
        yotm_posts = [] 

        for item in all_feed_items:
            post = item.get('post')
            
            # FILTRAGE 1 : Exclure les Reposts et les Réponses
            if item.get('reason') or (post and post.get('record', {}).get('reply')):
                continue 
            
            if post:
                
                # 🚩 FILTRAGE 2 : Vérification du Bornage Temporel
                created_at_str = post.get('record', {}).get('createdAt')
                if not created_at_str:
                    continue 

                post_date = localize_bluesky_timestamp(created_at_str, TARGET_TIMEZONE)
                
                if not post_date or post_date < time_cutoff:
                    # Le post est trop ancien ou la date est invalide, on passe
                    continue 
                
                # Ajout de la date localisée pour le JSON de sortie
                post['created_at_localized'] = post_date.isoformat()


                # FILTRAGE 3 : Logique de l'épingle (is_pinned)
                is_pinned = False
                if pinned_post_uri and post.get('uri') == pinned_post_uri:
                    is_pinned = True
                elif post.get('viewer', {}).get('pinned') is True:
                    is_pinned = True

                # Traitement si le post est épinglé
                if is_pinned:
                    post_text = post['record']['text']
                    cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                    post['record']['text'] = cleaned_text 
                    post['image_url'] = get_post_image_url(post)
                    
                    # Le post épinglé (s'il est récent) est ajouté ici
                    pinned_posts.append(post)
                    continue 
                
                # FILTRAGE 4 : Vérification du Tag Cible
                if not post_has_tag(post, TARGET_TAG):
                    continue 

                # --- Traitement des posts VALIDES, FILTRÉS (par tag et temps) ---
                
                post_text = post['record']['text']
                cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                post['record']['text'] = cleaned_text 

                post['image_url'] = get_post_image_url(post)
                
                yotm_posts.append(post)

        # 4. Sauvegarde finale du Fichier 2 : Le flux filtré (par tag et temps)
        save_data_to_json(yotm_posts, OUTPUT_FILTERED_FILE)
        
        # 5. Sauvegarde finale du Fichier 3 : Les posts épinglés (qui sont récents)
        if pinned_posts:
            save_data_to_json(pinned_posts, OUTPUT_PINNED_FILE)
        else:
             print(f"ℹ️ Aucune donnée à sauvegarder dans {OUTPUT_PINNED_FILE}. Fichier non créé.")


    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification ou du flux : {e}")
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

# --- Point d'Entrée ---
if __name__ == "__main__":
    fetch_bluesky_feed()