import requests
import frontmatter
import os
from datetime import datetime, timedelta, timezone
from slugify import slugify
import html2text
import pytz
import time
import shutil
from urllib.parse import urlparse
import re
# import json # Supprimé: Plus besoin de json

# --- Configuration ---
MASTODON_INSTANCE = "mastodon.social" # L'instance Mastodon
MASTODON_USERNAME = os.environ.get("MASTODON_USERNAME")
MASTODON_PASSWORD = os.environ.get("MASTODON_PASSWORD") # Ou MASTODON_ACCESS_TOKEN (si utilisé pour auth API)

OUTPUT_DIR = "_jobs"                  # Le dossier de votre collection Jekyll pour les jobs
# JOBS_DATA_FOR_PDF_FILE = os.path.join("scripts", "temp_jobs_for_pdf.json") # Supprimé: Plus besoin de ce chemin

TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

URL_REGEX = r"https?://[^\s]+" 

# NOUVEAU: Nombre de jours à récupérer
DAYS_TO_FETCH = 7 
# NOUVEAU: Limite de posts à récupérer par appel API (peut nécessiter pagination pour plus de jours/posts)
API_FETCH_LIMIT = 200 # Augmenté pour couvrir plus de jours. Max typique est 40, mais certaines instances autorisent plus.
                      # ATTENTION: Si ce n'est pas suffisant pour 7 jours de posts, la pagination sera nécessaire.

# --- Fonctions de nettoyage ---
def clean_output_directory(directory):
    """
    Supprime tous les fichiers et sous-dossiers dans le répertoire spécifié.
    Recrée ensuite le répertoire vide.
    """
    if os.path.exists(directory):
        print(f"Suppression du contenu existant dans '{directory}'...")
        shutil.rmtree(directory)
        print(f"Contenu de '{directory}' supprimé.")
    
    os.makedirs(directory)
    print(f"Dossier '{directory}' recréé.")

# --- Fonctions d'interaction avec l'API Mastodon ---
def get_account_id(instance, username):
    """Récupère l'ID numérique d'un compte Mastodon à partir de son nom d'utilisateur."""
    url = f"https://{instance}/api/v1/accounts/lookup?acct={username}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get('id')
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération de l'ID du compte '{username}' : {e}")
        return None

def get_account_statuses(instance, account_id, limit=API_FETCH_LIMIT): # Utilise la nouvelle limite
    """Récupère les statuts (posts) récents d'un compte Mastodon."""
    url = f"https://{instance}/api/v1/accounts/{account_id}/statuses"
    params = {
        'limit': limit,
        'exclude_replies': True, # Exclut les réponses
        'exclude_reblogs': True  # Exclut les reblogs
    }
    # Si vous utilisez un jeton d'accès:
    # headers = {'Authorization': f'Bearer {MASTODON_ACCESS_TOKEN}'}
    # response = requests.get(url, params=params, headers=headers)
    try:
        response = requests.get(url, params=params) 
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des statuts du compte ID {account_id} : {e}")
        return None

def create_jekyll_md_file_and_get_data(status_data):
    """
    Crée un fichier Markdown Jekyll à partir des données du statut Mastodon.
    Ne retourne plus les données pour le PDF.
    """
    raw_content = status_data.get('content', '')
    h = html2text.HTML2Text()
    h.ignore_links = True 
    h.ignore_images = True
    clean_content_raw_text = h.handle(raw_content).strip() 

    title = None
    card = status_data.get('card')
    if card and card.get('title'):
        title = card['title']
    else:
        # Essayer de prendre la première ligne non vide du contenu comme titre
        title_lines = [line.strip() for line in clean_content_raw_text.split('\n') if line.strip()]
        if title_lines:
            title = title_lines[0]
        else:
            title = f"Post Mastodon du {datetime.now().strftime('%Y-%m-%d')}" 

    description = None
    if card and card.get('description'):
        description = card['description'].strip()
    if not description: 
        description_from_toot_text = re.sub(URL_REGEX, '', clean_content_raw_text).strip()
        description = description_from_toot_text 

    pub_date_str = status_data.get('created_at')
    pub_date_utc = datetime.strptime(pub_date_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
    pub_date_local = pub_date_utc.astimezone(TARGET_TIMEZONE)
    jekyll_date = pub_date_local.strftime('%Y-%m-%d %H:%M:%S %z')

    tags = [tag['name'] for tag in status_data.get('tags', [])]
    if "mastodon" not in tags:
        tags.append("mastodon")

    url_article_reference = None
    domaine_article_reference = None

    if card and card.get('url'):
        url_article_reference = card['url']
        try:
            parsed_url = urlparse(url_article_reference)
            domaine_article_reference = parsed_url.netloc
        except Exception as e:
            print(f"Avertissement : Impossible de parser le domaine pour {url_article_reference} (carte): {e}")
            
    first_toot_link = None
    if clean_content_raw_text:
        matches = re.findall(URL_REGEX, clean_content_raw_text)
        if matches:
            first_toot_link = matches[0]
    
    fm = {
        'layout': 'job_post', 
        'title': title,
        'description': description, 
        'date': jekyll_date,
        'tags': tags,
        'mastodon_id': status_data.get('id'),
        'mastodon_url': status_data.get('url'),
        'mastodon_account': status_data.get('account', {}).get('acct'),
    }
    
    if url_article_reference:
        fm['url_article_reference'] = url_article_reference
    if domaine_article_reference:
        fm['domaine_article_reference'] = domaine_article_reference
    
    if first_toot_link:
        fm['first_toot_link'] = first_toot_link
        try:
            parsed_first_toot_link = urlparse(first_toot_link)
            fm['first_toot_link_domain'] = parsed_first_toot_link.netloc
        except Exception