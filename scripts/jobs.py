import requests
import frontmatter
import os
from datetime import datetime, timedelta, timezone
from slugify import slugify
import html2text
import pytz
import time
from urllib.parse import urlparse
import re
import shutil

# --- Configuration ---
MASTODON_INSTANCE = "mastodon.social"
MASTODON_USERNAME = os.environ.get("MASTODON_USERNAME") # CHANGEMENT ICI
MASTODON_PASSWORD = os.environ.get("MASTODON_PASSWORD") # CHANGEMENT ICI

OUTPUT_DIR = "_jobs" # Cible la collection _news

TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

URL_REGEX = r"https?://[^\s]+" 

DAYS_TO_FETCH = 30 
API_FETCH_LIMIT = 200 

# --- Fonctions de nettoyage (inchangées) ---
def clean_output_directory(directory):
    if os.path.exists(directory):
        print(f"Suppression du contenu existant dans '{directory}'...")
        shutil.rmtree(directory)
        print(f"Contenu de '{directory}' supprimé.")
    
    os.makedirs(directory)
    print(f"Dossier '{directory}' recréé.")

# --- Fonctions d'interaction avec l'API Mastodon (inchangées) ---
def get_account_id(instance, username):
    url = f"https://{instance}/api/v1/accounts/lookup?acct={username}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json().get('id')
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération de l'ID du compte '{username}' : {e}")
        return None
    except Exception as e:
        print(f"Une erreur inattendue s'est produite lors de la récupération de l'ID : {e}")
        return None

def get_account_statuses(instance, account_id, limit=API_FETCH_LIMIT):
    url = f"https://{instance}/api/v1/accounts/{account_id}/statuses"
    params = {
        'limit': limit,
        'exclude_replies': True,
        'exclude_reblogs': True
    }
    try:
        response = requests.get(url, params=params) 
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des statuts du compte ID {account_id} : {e}")
        return None
    except Exception as e:
        print(f"Une erreur inattendue s'est produite lors de la récupération des statuts : {e}")
        return None

def get_mastodon_oembed_html(instance_url, status_url):
    """
    Récupère le code HTML d'intégration (oEmbed) d'un statut Mastodon
    et y injecte l'attribut loading="lazy".
    """
    oembed_url = f"https://{instance_url}/api/oembed"
    params = {'url': status_url, 'hide_thread': True, 'hide_media': False}
    try:
        response = requests.get(oembed_url, params=params, timeout=10)
        response.raise_for_status()
        oembed_data = response.json()
        html_embed = oembed_data.get('html')
        
        if html_embed:
            html_embed = re.sub(r'<iframe(?=\s|>)([^>]*)>', r'<iframe\1 loading="lazy">', html_embed, 1)
        
        return html_embed
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération du code oEmbed pour {status_url} : {e}")
        return None
    except Exception as e:
        print(f"Une erreur inattendue s'est produite lors de l'oEmbed pour {status_url} : {e}")
        return None

# --- Fonction principale de création des fichiers MD (inchangée dans sa logique) ---
def create_jekyll_md_file_and_get_data(status_data):
    raw_content = status_data.get('content', '')
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    clean_content_raw_text = h.handle(raw_content).strip()

    # PARTIE 1: Extraction des infos nécessaires pour le Front Matter
    url_article_reference = None
    domaine_article_reference = None 
    card = status_data.get('card')
    if card and card.get('url'):
        url_article_reference = card['url']
        try:
            parsed_url = urlparse(url_article_reference)
            domaine_article_reference = parsed_url.netloc
        except Exception as e:
            print(f"Avertissement : Impossible de parser le domaine pour {url_article_reference} (carte): {e}")
    
    # PARTIE 2: Préparation du contenu textuel (pour le titre/fallback éventuel)
    content_text_only = re.sub(URL_REGEX, '', clean_content_raw_text).strip()

    # PARTIE 3: Détermination du titre
    title = None
    if card and card.get('title'):
        title = card['title'] # Titre de l'article de référence (priorité)
    else:
        title_lines = [line.strip() for line in content_text_only.split('\n') if line.strip()]
        if title_lines:
            title = title_lines[0]
        else:
            title = f"Post Mastodon du {datetime.now().strftime('%Y-%m-%d')}"

    description = None 
    if card and card.get('description'):
        description = card['description'].strip()
    if not description:
        description = content_text_only

    pub_date_str = status_data.get('created_at')
    pub_date_utc = datetime.strptime(pub_date_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
    pub_date_local = pub_date_utc.astimezone(TARGET_TIMEZONE)
    jekyll_date = pub_date_local.strftime('%Y-%m-%d %H:%M:%S %z')

    # PARTIE 4: CONSTRUCTION DU FRONT MATTER (fm) - Minimal et Fonctionnel
    fm = {
        'layout': 'news_item', # Layout pour les articles d'actualité Mastodon
        'title': title,        # Titre de l'article de référence (selon votre demande)
        'date': jekyll_date,   # INDISPENSABLE pour Jekyll (tri, build)
        'mastodon_id': status_data.get('id'), # ID du toot (selon votre demande)
        'mastodon_url': status_data.get('url'), # URL complète du toot (nécessaire pour l'embed)
        'mastodon_account': status_data.get('account', {}).get('acct'), # Compte de l'auteur (nécessaire pour l'embed)
        'mastodon_instance': MASTODON_INSTANCE, # Instance Mastodon (nécessaire pour l'embed)
        # 'description': description # Commenté pour minimalisme (si non utilisé dans layout)
        # 'url_article_reference' et 'domaine_article_reference' ajoutés si vous les voulez dans le FM
    }
    
    if url_article_reference:
        fm['url_article_reference'] = url_article_reference
    if domaine_article_reference:
        fm['domaine_article_reference'] = domaine_article_reference

    
    # PARTIE 5: Assemblage final du contenu et écriture du fichier
    toot_embed_html = get_mastodon_oembed_html(MASTODON_INSTANCE, status_data.get('url'))

    markdown_content = "" # Le corps du Markdown est vide (rempli par le layout)

    if toot_embed_html:
        markdown_content += '<div class="mastodon-embed-wrapper">\n'
        markdown_content += toot_embed_html + '\n'
        markdown_content += '</div>\n\n'
    else:
        print(f"Avertissement: Impossible de récupérer le code d'intégration pour le toot {status_data.get('url')}. Ajout du texte brut à la place.")
        markdown_content += content_text_only + "\n\n"


    filename_slug = str(status_data.get('id'))
    filename = f"{pub_date_local.strftime('%Y-%m-%d')}-{filename_slug}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    post_with_fm = frontmatter.Post(markdown_content)
    post_with_fm.metadata = fm

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post_with_fm))
        print(f"Article '{filename}' créé avec succès dans '{OUTPUT_DIR}'.")
        return True
    except IOError as e:
        print(f"Erreur lors de l'écriture du fichier '{filename}': {e}")
        return False

# --- Exécution principale ---
if __name__ == "__main__":
    print("--- Démarrage du processus de récupération des posts Mastodon ---")
    
    # CHANGEMENT ICI : Utilisation des noms de variables d'environnement mis à jour
    if not MASTODON_USERNAME or not MASTODON_PASSWORD:
        print("Erreur: Les variables MASTODON_USERNAME ou MASTODON_PASSWORD (token) ne sont pas définies en tant que variables d'environnement.")
        print("Veuillez les configurer dans les Secrets GitHub de votre dépôt.")
        exit(1)

    clean_output_directory(OUTPUT_DIR)

    print(f"Tentative de récupération des posts du profil '{MASTODON_USERNAME}' depuis l'instance '{MASTODON_INSTANCE}'.")
    
    # CHANGEMENT ICI : Utilisation des noms de variables d'environnement mis à jour
    account_id = get_account_id(MASTODON_INSTANCE, MASTODON_USERNAME)

    if account_id:
        print(f"ID numérique pour '{MASTODON_USERNAME}' : {account_id}")
        
        now_utc = datetime.now(timezone.utc)
        start_date_utc = now_utc - timedelta(days=DAYS_TO_FETCH)
        start_date_utc = datetime(start_date_utc.year, start_date_utc.month, start_date_utc.day, 0, 0, 0, tzinfo=timezone.utc)
        
        print(f"Récupération des posts publiés depuis : {start_date_utc.astimezone(TARGET_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')} (soit les {DAYS_TO_FETCH} derniers jours)")

        statuses = get_account_statuses(MASTODON_INSTANCE, account_id, limit=API_FETCH_LIMIT) 
        
        if statuses:
            processed_count = 0
            statuses.sort(key=lambda x: x.get('created_at'), reverse=True)

            for status in statuses:
                status_created_at_str = status.get('created_at')
                status_date_utc = datetime.strptime(status_created_at_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)

                if status_date_utc >= start_date_utc:
                    if create_jekyll_md_file_and_get_data(status):
                        processed_count += 1
                else:
                    print(f"Post '{status.get('url')}' est plus ancien que la période de {DAYS_TO_FETCH} jours. Arrêt du traitement des posts API.")
                    break
                
                time.sleep(0.5)
            
            if processed_count == 0:
                print(f"Aucun nouveau post trouvé pour la période des {DAYS_TO_FETCH} derniers jours pour le profil '{MASTODON_USERNAME}'.")
            else:
                print(f"{processed_count} post(s) créé(s) dans '{OUTPUT_DIR}' pour la période des {DAYS_TO_FETCH} derniers jours.")
        else:
            print(f"Aucun statut trouvé pour le profil '{MASTODON_USERNAME}'.")
    else:
        print(f"Impossible de trouver l'ID numérique pour le profil '{MASTODON_USERNAME}'. Vérifiez le nom d'utilisateur et l'instance.")
    
    print("--- Processus Mastodon terminé ---")