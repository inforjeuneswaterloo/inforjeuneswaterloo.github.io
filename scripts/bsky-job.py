import requests
import json
import os
import pytz
import re
import datetime 
import time
import feedparser  # Assure-toi que 'feedparser' est dans ton requirements.txt
from requests.exceptions import HTTPError, ConnectionError, Timeout

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
USERNAME = os.environ.get("BLUESKY_JOB_USERNAME")
PASSWORD = os.environ.get("BLUESKY_JOB_PASSWORD") 
BLUESKY_DID = os.environ.get("BLUESKY_JOB_DID_PLC") 

# Configuration Substack
SUBSTACK_RSS_URL = "https://ijwaterloo.substack.com/feed"

# Configuration du fichier de sortie et du filtre
DATA_DIR = "_data"
TARGET_TAG = "ij1410" 
OUTPUT_FILTERED_FILE = os.path.join(DATA_DIR, f"bluesky_jobs_waterloo_posts.json") 
OUTPUT_ALL_FILE = os.path.join(DATA_DIR, "bluesky_job_posts.json")
OUTPUT_PINNED_FILE = os.path.join(DATA_DIR, "bsky_posts_pinned.json") 
OUTPUT_SUBSTACK_FILE = os.path.join(DATA_DIR, "substack_veille_presse.json")

TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

# URL de l'API Bluesky
API_PDS = "https://bsky.social"
FEED_LIMIT = 10 # Augmenté légèrement pour capter plus de posts si besoin

# Regex pour identifier les URLs
URL_REGEX = r"https?://[^\s]+|www\.[^\s]+" 

# --- Variables Globales pour le Jeton ---
global_access_jwt = None
global_refresh_jwt = None

# -------------------------- FONCTIONS UTILITAIRES --------------------------

def clean_data_directory(directory):
    """Crée le répertoire _data s'il n'existe pas."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def localize_bluesky_timestamp(timestamp_str, target_tz):
    """Convertit une chaîne de temps Bluesky (UTC) en objet datetime localisé."""
    try:
        dt_utc_naive = datetime.datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        dt_utc_aware = pytz.utc.localize(dt_utc_naive)
        dt_localized = dt_utc_aware.astimezone(target_tz)
        return dt_localized
    except Exception:
        return None

def get_post_image_url(post):
    """Tente d'extraire l'URL de la vignette d'un post Bluesky."""
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
    """Vérifie si un post Bluesky contient le hashtag cible."""
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
    """Sauvegarde la liste des posts dans le fichier JSON spécifié."""
    clean_data_directory(DATA_DIR)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        print(f"✅ Succès : {len(data_list)} entrées enregistrées dans {output_path}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture de {output_path}: {e}")
        return False

def refresh_session(session, current_refresh_jwt):
    """Rafraîchit la session Bluesky."""
    refresh_url = f"{API_PDS}/xrpc/com.atproto.server.refreshSession"
    refresh_headers = {"Authorization": f"Bearer {current_refresh_jwt}"}
    global global_access_jwt, global_refresh_jwt
    try:
        response = session.post(refresh_url, headers=refresh_headers)
        response.raise_for_status()
        new_data = response.json()
        global_access_jwt = new_data.get('accessJwt')
        global_refresh_jwt = new_data.get('refreshJwt') or current_refresh_jwt
        return True
    except Exception:
        return False

def get_pinned_post_uri(session, did, headers):
    """Récupère l'URI du post épinglé Bluesky."""
    profile_url = f"{API_PDS}/xrpc/app.bsky.actor.getProfile?actor={did}"
    try:
        response = session.get(profile_url, headers=headers)
        response.raise_for_status()
        return response.json().get('pinnedPost') 
    except:
        return None

# -------------------------- FONCTION SUBSTACK RSS --------------------------

def fetch_substack_feed():
    """Récupère les articles de Substack via RSS."""
    print(f"📡 Analyse du flux Substack : {SUBSTACK_RSS_URL}")
    try:
        feed = feedparser.parse(SUBSTACK_RSS_URL)
        if not feed.entries:
            print("⚠️ Flux Substack vide.")
            return

        substack_posts = []
        for entry in feed.entries[:5]: # On garde les 5 derniers articles
            # Nettoyage des balises HTML envoyées par Substack dans le résumé
            summary_clean = re.sub(r'<[^>]+>', '', entry.summary).strip()
            
            substack_posts.append({
                'title': entry.title,
                'url': entry.link,
                'published': entry.published,
                'summary': summary_clean[:180] + "..." if len(summary_clean) > 180 else summary_clean
            })
        
        save_data_to_json(substack_posts, OUTPUT_SUBSTACK_FILE)
    except Exception as e:
        print(f"❌ Erreur lors de l'extraction Substack : {e}")

# -------------------------- FONCTION BLUESKY --------------------------

def fetch_bluesky_feed():
    """Authentifie et traite le flux Bluesky pour Jekyll."""
    if not all([USERNAME, PASSWORD, BLUESKY_DID]):
        print("❌ Erreur : Identifiants Bluesky manquants dans l'environnement.")
        return

    session = requests.Session()
    auth_url = f"{API_PDS}/xrpc/com.atproto.server.createSession"
    auth_payload = {"identifier": USERNAME, "password": PASSWORD}
    global global_access_jwt, global_refresh_jwt
    
    try:
        auth_response = session.post(auth_url, json=auth_payload)
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        global_access_jwt = auth_data.get('accessJwt')
        global_refresh_jwt = auth_data.get('refreshJwt')

        time_limit_days = 7 
        now_localized = datetime.datetime.now(TARGET_TIMEZONE)
        time_cutoff = now_localized - datetime.timedelta(days=time_limit_days)
        
        headers = {"Authorization": f"Bearer {global_access_jwt}"}
        FEED_URL = f"{API_PDS}/xrpc/app.bsky.feed.getAuthorFeed?actor={BLUESKY_DID}&limit={FEED_LIMIT}"
        
        feed_response = session.get(FEED_URL, headers=headers, timeout=15)
        feed_response.raise_for_status()
        data = feed_response.json()

        pinned_post_uri = get_pinned_post_uri(session, BLUESKY_DID, headers)
        all_feed_items = data.get('feed', [])
        
        # Sauvegarde brute
        all_posts_data = [item.get('post') for item in all_feed_items if item.get('post')]
        save_data_to_json(all_posts_data, OUTPUT_ALL_FILE)

        filtered_posts_by_tag = [] 
        pinned_posts = [] 

        for item in all_feed_items:
            post = item.get('post')
            if item.get('reason') or (post and post.get('record', {}).get('reply')):
                continue 
            if post:
                created_at_str = post.get('record', {}).get('createdAt')
                post_date = localize_bluesky_timestamp(created_at_str, TARGET_TIMEZONE)
                if not post_date or post_date < time_cutoff: continue
                
                post['created_at_localized'] = post_date.isoformat()
                is_pinned = (pinned_post_uri and post.get('uri') == pinned_post_uri) or post.get('viewer', {}).get('pinned') is True
                
                # Nettoyage texte (retrait des URLs brutes) et extraction vignette
                post_text = post['record']['text']
                post['record']['text'] = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                post['image_url'] = get_post_image_url(post)

                if is_pinned:
                    pinned_posts.append(post)
                elif post_has_tag(post, TARGET_TAG):
                    filtered_posts_by_tag.append(post)

        save_data_to_json(filtered_posts_by_tag, OUTPUT_FILTERED_FILE)
        if pinned_posts: save_data_to_json(pinned_posts, OUTPUT_PINNED_FILE)

    except Exception as e:
        print(f"❌ Erreur Bluesky : {e}")

# -------------------------- EXÉCUTION --------------------------

if __name__ == "__main__":
    # Traitement séquentiel des deux sources
    fetch_bluesky_feed()
    fetch_substack_feed()