import requests
import json
import os
import pytz
import re
import datetime 
import time
from requests.exceptions import HTTPError, ConnectionError, Timeout

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

# Regex pour identifier les URLs
URL_REGEX = r"https?://[^\s]+|www\.[^\s]+" 

# --- Variables Globales pour le Jeton (à gérer par la fonction principale) ---
global_access_jwt = None
global_refresh_jwt = None

# --- Fonctions Utilitaires (inchangées) ---
def clean_data_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def localize_bluesky_timestamp(timestamp_str, target_tz):
    try:
        dt_utc_naive = datetime.datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        dt_utc_aware = pytz.utc.localize(dt_utc_naive)
        dt_localized = dt_utc_aware.astimezone(target_tz)
        return dt_localized
    except Exception:
        return None

def get_post_image_url(post):
    embed = post.get('embed')
    if not embed: return None
    embed_type = embed.get('$type')
    if embed_type == 'app.bsky.embed.images':
        images = embed.get('images')
        if images and len(images) > 0: return images[0].get('thumb') 
    elif embed_type == 'app.bsky.embed.recordWithMedia':
        media = embed.get('media')
        if media and media.get('$type') == 'app.bsky.embed.images':
            images = media.get('images')
            if images and len(images) > 0: return images[0].get('thumb')
    elif embed_type == 'app.bsky.embed.external#view' or embed_type == 'app.bsky.embed.external':
        external = embed.get('external')
        if external and external.get('thumb'): return external.get('thumb')
    return None

def post_has_tag(post, target_tag):
    facets = post.get('record', {}).get('facets')
    if not facets: return False
    normalized_target_tag = target_tag.lower().lstrip('#')
    for facet in facets:
        for feature in facet.get('features', []):
            if feature.get('$type') == 'app.bsky.richtext.facet#tag':
                tag = feature.get('tag')
                if tag and tag.lower() == normalized_target_tag: return True
    return False

def save_data_to_json(data_list, output_path):
    clean_data_directory(DATA_DIR)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        print(f"✅ Succès : {len(data_list)} posts sauvegardés dans {output_path}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture du fichier JSON '{output_path}': {e}")
        return False

# --- NOUVELLE FONCTION : Rafraîchissement du Jeton ---
def refresh_session(session, current_refresh_jwt):
    """Utilise le refresh token pour obtenir un nouvel access token."""
    refresh_url = f"{API_PDS}/xrpc/com.atproto.server.refreshSession"
    refresh_headers = {"Authorization": f"Bearer {current_refresh_jwt}"}
    
    try:
        response = session.post(refresh_url, headers=refresh_headers)
        response.raise_for_status()
        new_data = response.json()
        
        # Mettre à jour les jetons globaux
        global global_access_jwt
        global global_refresh_jwt

        global_access_jwt = new_data.get('accessJwt')
        # Le refresh token peut aussi être mis à jour
        global_refresh_jwt = new_data.get('refreshJwt') or current_refresh_jwt
        
        print("✅ Jeton d'accès rafraîchi avec succès.")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Échec du rafraîchissement : Jeton de rafraîchissement invalide ou expiré.")
        else:
            print(f"❌ Erreur HTTP lors du rafraîchissement du jeton : {e}")
        return False

# --- Fonction Principale Modifiée ---
def fetch_bluesky_feed():
    """Authentifie, récupère le flux, filtre par tag et temps, recherche le post épinglé et sauvegarde les trois fichiers."""
    
    if not all([USERNAME, PASSWORD, BLUESKY_DID]):
        print("❌ Erreur de configuration : Un ou plusieurs identifiants Bluesky sont manquants.")
        return

    session = requests.Session()
    auth_url = f"{API_PDS}/xrpc/com.atproto.server.createSession"
    auth_payload = {"identifier": USERNAME, "password": PASSWORD}
    
    global global_access_jwt
    global global_refresh_jwt
    
    try:
        # 1. Authentification initiale (obtenir les deux jetons)
        auth_response = session.post(auth_url, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        
        global_access_jwt = auth_data.get('accessJwt')
        global_refresh_jwt = auth_data.get('refreshJwt') # <-- Le jeton de rafraîchissement est essentiel!

        print(f"✅ Authentification réussie. Récupération du flux (limite: {FEED_LIMIT})...")

        # 🚩 Bornage Temporel : Calcul de la date limite (-7 jours)
        time_limit_days = 7 
        now_localized = datetime.datetime.now(TARGET_TIMEZONE)
        time_cutoff = now_localized - datetime.timedelta(days=time_limit_days)
        print(f"⏰ Bornage actif : Ne conserver que les posts postérieurs au {time_cutoff.strftime('%Y-%m-%d %H:%M:%S %Z')}.")

        
        # 2. Logique de Récupération du Flux avec Résilience (Retries)
        
        max_attempts = 3
        data = None
        
        for attempt in range(max_attempts):
            
            # Construire l'en-tête avec le jeton d'accès actuel
            headers = {"Authorization": f"Bearer {global_access_jwt}"}
            FEED_URL = f"{API_PDS}/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_DID}&limit={FEED_LIMIT}"
            
            try:
                # 3. Appel API du flux
                feed_response = session.get(FEED_URL, headers=headers, timeout=15)
                feed_response.raise_for_status()
                data = feed_response.json()
                print(f"✅ Flux récupéré à la tentative {attempt + 1}.")
                break # Succès, sortir de la boucle

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code
                
                if status == 401:
                    # 🚨 GESTION DE L'EXPIRATION DU JWT : Tenter de rafraîchir
                    print("⚠️ Erreur 401: Jeton expiré ou invalide. Tentative de rafraîchissement...")
                    if global_refresh_jwt and refresh_session(session, global_refresh_jwt):
                        # Le jeton a été rafraîchi, on continue la boucle pour réessayer immédiatement
                        continue
                    else:
                        print("❌ Échec du rafraîchissement. Impossible de continuer.")
                        return

                elif status in [502, 503, 504]:
                    # 🌐 GESTION DES ERREURS SERVEUR : Tenter de réessayer
                    if attempt < max_attempts - 1:
                        wait_time = 2 ** (attempt + 1)
                        print(f"❌ Erreur HTTP {status} (Serveur). Nouvelle tentative dans {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Échec persistant du serveur après {max_attempts} tentatives.")
                        return
                
                else:
                    # Autres erreurs non gérables (400, 404, etc.)
                    print(f"❌ Erreur HTTP inattendue ({status}): {e}")
                    return
        
        if not data:
            print("❌ Aucune donnée de flux récupérée après toutes les tentatives.")
            return

        # --- DÉBUT DU TRAITEMENT DES DONNÉES (inchangé) ---
        all_feed_items = data.get('feed', [])
        
        # Le reste de votre logique de filtrage et sauvegarde...
        # ... (La suite du code pour le filtrage par pin et tag, tel que vous l'aviez)
        # ...
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP lors de l'authentification : {e}")
    except Exception as e:
        print(f"❌ Une erreur inattendue s'est produite : {e}")

# --- Point d'Entrée ---
if __name__ == "__main__":
    fetch_bluesky_feed()