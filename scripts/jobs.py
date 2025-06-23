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
import shutil # Ajouté, car utilisé dans clean_output_directory

# --- Configuration ---
MASTODON_INSTANCE = "mastodon.social" # L'instance Mastodon
MASTODON_USERNAME = os.environ.get("MASTODON_USERNAME")
MASTODON_PASSWORD = os.environ.get("MASTODON_PASSWORD") # Ou MASTODON_ACCESS_TOKEN (si utilisé pour auth API)

OUTPUT_DIR = "_jobs"                  # Le dossier de votre collection Jekyll pour les jobs

TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

URL_REGEX = r"https?://[^\s]+" # Expression régulière pour trouver les URLs dans le texte

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
    except Exception as e:
        print(f"Une erreur inattendue s'est produite lors de la récupération de l'ID : {e}")
        return None

def get_account_statuses(instance, account_id, limit=API_FETCH_LIMIT):
    """Récupère les statuts (posts) récents d'un compte Mastodon."""
    url = f"https://{instance}/api/v1/accounts/{account_id}/statuses"
    params = {
        'limit': limit,
        'exclude_replies': True,
        'exclude_reblogs': True
    }
    # Si vous utilisez un jeton d'accès (RECOMMANDÉ pour la sécurité):
    # MASTODON_ACCESS_TOKEN = os.environ.get("MASTODON_ACCESS_TOKEN")
    # headers = {'Authorization': f'Bearer {MASTODON_ACCESS_TOKEN}'}
    # response = requests.get(url, params=params, headers=headers)
    # else:
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

def create_jekyll_md_file_and_get_data(status_data):
    """
    Crée un fichier Markdown Jekyll à partir des données du statut Mastodon.
    Les liens d'article et les premiers liens du toot sont conservés dans le front matter,
    mais supprimés du corps du texte du post.
    Retourne True si le fichier a été créé avec succès, False sinon.
    """
    raw_content = status_data.get('content', '')
    h = html2text.HTML2Text()
    h.ignore_links = True # Tente d'ignorer les balises HTML <a>
    h.ignore_images = True
    clean_content_raw_text = h.handle(raw_content).strip()

    # --- PARTIE 1: EXTRACTION DES LIENS ET INFOS POUR LE FRONT MATTER ---
    # Ces liens sont extraits AVANT le nettoyage complet du texte pour s'assurer qu'on les capture
    # pour le front matter, même s'ils seront retirés du corps du texte.
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

    first_toot_link = None
    # Recherche du premier lien DIRECTEMENT dans le clean_content_raw_text
    # pour le conserver dans le front matter.
    if clean_content_raw_text:
        matches = re.findall(URL_REGEX, clean_content_raw_text)
        if matches:
            first_toot_link = matches[0]

    # --- PARTIE 2: PRÉPARATION DU CONTENU TEXTUEL POUR LE CORPS DU POST ---
    # C'est LA LIGNE CLÉ : Supprimer toutes les URLs du texte qui sera écrit dans le corps du Markdown.
    content_for_markdown_body = re.sub(URL_REGEX, '', clean_content_raw_text).strip()

    # --- PARTIE 3: DÉTERMINATION DU TITRE ET DE LA DESCRIPTION ---
    title = None
    if card and card.get('title'):
        title = card['title']
    else:
        # Baser le titre sur le contenu sans URLs pour éviter un titre qui serait juste une URL
        title_lines = [line.strip() for line in content_for_markdown_body.split('\n') if line.strip()]
        if title_lines:
            title = title_lines[0]
        else:
            title = f"Post Mastodon du {datetime.now().strftime('%Y-%m-%d')}"

    description = None
    if card and card.get('description'):
        description = card['description'].strip()
    if not description:
        # La description est basée sur le contenu sans URLs
        description = content_for_markdown_body

    pub_date_str = status_data.get('created_at')
    pub_date_utc = datetime.strptime(pub_date_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
    pub_date_local = pub_date_utc.astimezone(TARGET_TIMEZONE)
    jekyll_date = pub_date_local.strftime('%Y-%m-%d %H:%M:%S %z')

    tags = [tag['name'] for tag in status_data.get('tags', [])]
    if "mastodon" not in tags:
        tags.append("mastodon")

    # --- PARTIE 4: CONSTRUCTION DU FRONT MATTER (fm) ---
    # Ici, nous incluons tous les liens que nous voulons conserver dans le front matter.
    fm = {
        'layout': 'post', 
        'title': title,
        'description': description, 
        'date': jekyll_date,
        'tags': tags,
        'mastodon_id': status_data.get('id'),
        'mastodon_url': status_data.get('url'),
        'mastodon_account': status_data.get('account', {}).get('acct'),
    }
    
    if url_article_reference: # Lien de la carte Mastodon (conservé dans le FM)
        fm['url_article_reference'] = url_article_reference
    if domaine_article_reference:
        fm['domaine_article_reference'] = domaine_article_reference
    
    if first_toot_link: # Premier lien trouvé dans le corps du toot (conservé dans le FM)
        fm['first_toot_link'] = first_toot_link
        try:
            parsed_first_toot_link = urlparse(first_toot_link)
            fm['first_toot_link_domain'] = parsed_first_toot_link.netloc
        except Exception as e:
            print(f"Avertissement : Impossible de parser le domaine pour le premier lien du toot ({first_toot_link}): {e}")

    # --- PARTIE 5: ASSEMBLAGE FINAL ET ÉCRITURE DU FICHIER ---
    # Le corps du Markdown utilise le contenu nettoyé (sans URLs).
    markdown_content = content_for_markdown_body + "\n\n"
        
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
    
    if not MASTODON_USERNAME or not MASTODON_PASSWORD:
        print("Erreur: Les variables MASTODON_USERNAME ou MASTODON_PASSWORD (token) ne sont pas définies en tant que variables d'environnement.")
        print("Veuillez les configurer dans les Secrets GitHub de votre dépôt.")
        exit(1)

    clean_output_directory(OUTPUT_DIR)

    print(f"Tentative de récupération des posts du profil '{MASTODON_USERNAME}' depuis l'instance '{MASTODON_INSTANCE}'.")
    
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