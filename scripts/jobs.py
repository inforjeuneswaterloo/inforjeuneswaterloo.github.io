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
import json # NOUVEAU: Import pour la gestion des fichiers JSON

# --- Configuration ---
MASTODON_INSTANCE = "mastodon.social" # L'instance Mastodon
# Lisez les identifiants depuis les variables d'environnement (SÉCURISÉ)
MASTODON_USERNAME = os.environ.get("MASTODON_USERNAME")
MASTODON_PASSWORD = os.environ.get("MASTODON_PASSWORD") # Ou MASTODON_ACCESS_TOKEN (si utilisé pour auth API)

OUTPUT_DIR = "_jobs"                  # Le dossier de votre collection Jekyll pour les jobs
# Chemin du fichier JSON temporaire pour les données de jobs à utiliser pour le PDF
JOBS_DATA_FOR_PDF_FILE = os.path.join("scripts", "temp_jobs_for_pdf.json")

# Définissez le fuseau horaire pour la date de publication des posts Jekyll
TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 

# Regular expression to find URLs in text (used for cleaning description)
URL_REGEX = r"https?://[^\s]+" 

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

def get_account_statuses(instance, account_id, limit=40):
    """Récupère les statuts (posts) récents d'un compte Mastodon."""
    url = f"https://{instance}/api/v1/accounts/{account_id}/statuses"
    params = {
        'limit': limit,
        'exclude_replies': True, # Exclut les réponses
        'exclude_reblogs': True  # Exclut les reblogs
    }
    try:
        response = requests.get(url, params=params) 
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la récupération des statuts du compte ID {account_id} : {e}")
        return None

def create_jekyll_md_file_and_get_data(status_data):
    """
    Crée un fichier Markdown Jekyll à partir des données du statut Mastodon
    et retourne le front matter formaté pour un usage externe (ex: PDF).
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
        title_from_content = clean_content_raw_text.split('\n')[0].strip()
        if title_from_content:
            title = title_from_content
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
        except Exception as e:
            print(f"Avertissement : Impossible de parser le domaine pour le premier lien du toot ({first_toot_link}): {e}")

    markdown_content = clean_content_raw_text + "\n\n" 
    
    if url_article_reference and url_article_reference != status_data.get('url'):
        markdown_content += f"[Consulter l'article original]({url_article_reference})\n\n"
    elif first_toot_link and first_toot_link != status_data.get('url'):
        markdown_content += f"[Consulter le lien trouvé dans le post]({first_toot_link})\n\n"
    elif status_data.get('url'):
        markdown_content += f"[Voir le post Mastodon original]({status_data.get('url')})\n\n"
        
    filename_slug = str(status_data.get('id'))
    filename = f"{pub_date_local.strftime('%Y-%m-%d')}-{filename_slug}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)

    post_with_fm = frontmatter.Post(markdown_content)
    post_with_fm.metadata = fm

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(frontmatter.dumps(post_with_fm))
        print(f"Article '{filename}' créé avec succès dans '{OUTPUT_DIR}'.")
        return fm # Retourne le front matter du job créé
    except IOError as e:
        print(f"Erreur lors de l'écriture du fichier '{filename}': {e}")
        return None

# --- Exécution principale ---
if __name__ == "__main__":
    print("--- Démarrage du processus de récupération des posts Mastodon ---")
    
    # Vérifiez que les identifiants sont bien chargés des variables d'environnement
    if not MASTODON_USERNAME or not MASTODON_PASSWORD:
        print("Erreur: Les variables MASTODON_USERNAME ou MASTODON_PASSWORD (token) ne sont pas définies en tant que variables d'environnement.")
        print("Veuillez les configurer dans les Secrets GitHub de votre dépôt.")
        exit(1)

    # ÉTAPE 1: Nettoyer le dossier _jobs existant
    clean_output_directory(OUTPUT_DIR)

    # ÉTAPE 2: Récupérer et créer les nouveaux articles
    print(f"Tentative de récupération des posts du profil '{MASTODON_USERNAME}' depuis l'instance '{MASTODON_INSTANCE}'.")
    
    account_id = get_account_id(MASTODON_INSTANCE, MASTODON_USERNAME)

    if account_id:
        print(f"ID numérique pour '{MASTODON_USERNAME}' : {account_id}")
        
        now_utc = datetime.now(timezone.utc)
        start_of_today_utc = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
        print(f"Récupération des posts publiés depuis : {start_of_today_utc.astimezone(TARGET_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')}")

        statuses = get_account_statuses(MASTODON_INSTANCE, account_id, limit=40) 
        
        processed_job_data_for_pdf = [] # Initialise la liste pour les données du PDF

        if statuses:
            processed_count = 0
            for status in statuses:
                status_created_at_str = status.get('created_at')
                status_date_utc = datetime.strptime(status_created_at_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)

                if status_date_utc >= start_of_today_utc:
                    # Appelle la nouvelle fonction qui crée le MD et retourne le front matter
                    job_fm = create_jekyll_md_file_and_get_data(status)
                    if job_fm: # Si le fichier MD a été créé avec succès
                        processed_job_data_for_pdf.append(job_fm) # Ajoute le front matter à la liste
                        processed_count += 1
                else:
                    print(f"Post '{status.get('url')}' est plus ancien que le jour actuel ({status_date_utc.astimezone(TARGET_TIMEZONE).strftime('%Y-%m-%d')}), et les suivants le seront aussi. Arrêt du traitement.")
                    break
                
                time.sleep(0.5)
            
            if processed_count == 0:
                print(f"Aucun nouveau post trouvé pour le jour actuel ({now_utc.astimezone(TARGET_TIMEZONE).strftime('%Y-%m-%d')}) pour le profil '{MASTODON_USERNAME}'.")
            else:
                print(f"{processed_count} post(s) créé(s) dans '{OUTPUT_DIR}' pour le jour actuel.")
        else:
            print(f"Aucun statut trouvé pour le profil '{MASTODON_USERNAME}'.")
    else:
        print(f"Impossible de trouver l'ID numérique pour le profil '{MASTODON_USERNAME}'. Vérifiez le nom d'utilisateur et l'instance.")
    
    # --- NOUVEAU : Écrire les données des jobs dans un fichier JSON pour le PDF ---
    if processed_job_data_for_pdf:
        pdf_data_path = JOBS_DATA_FOR_PDF_FILE
        with open(pdf_data_path, "w", encoding="utf-8") as f:
            json.dump(processed_job_data_for_pdf, f, ensure_ascii=False, indent=2)
        print(f"Données de {len(processed_job_data_for_pdf)} jobs écrites dans {pdf_data_path} pour le PDF.")
    else:
        print(f"Aucune donnée de job du jour à écrire dans {JOBS_DATA_FOR_PDF_FILE}.")
        # Créer un fichier JSON vide si aucun job n'a été traité, pour éviter des erreurs au script suivant
        with open(JOBS_DATA_FOR_PDF_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


    print("--- Processus Mastodon terminé ---")