import requests
import json
import os
from datetime import datetime, timedelta, timezone 
import html2text
import pytz
import time
from urllib.parse import urlparse
import re
import shutil

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
MASTODON_INSTANCE = "mastodon.social"
MASTODON_USERNAME = os.environ.get("MASTODON_USERNAME")
MASTODON_API_TOKEN = os.environ.get("MASTODON_PASSWORD") 

# Configuration du fichier de sortie
DATA_DIR = "_data"
OUTPUT_JSON_FILE = os.path.join(DATA_DIR, "mastodon_posts.json")

TARGET_TIMEZONE = pytz.timezone('Europe/Brussels') 
URL_REGEX = r"https?://[^\s]+" 
API_FETCH_LIMIT = 80 # Limite par page, peut être ajustée jusqu'à 80 pour Mastodon
DAYS_TO_FETCH = 7 # Période de récupération

# --- Fonctions de Nettoyage ---
def clean_data_directory(directory):
    """Crée le répertoire _data s'il n'existe pas."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Dossier '{directory}' créé.")
    else:
        print(f"Dossier '{directory}' existe déjà.")

# --- Fonctions d'Interaction avec l'API Mastodon ---
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

def get_account_statuses(instance, account_id, api_token, start_date_utc, limit=API_FETCH_LIMIT):
    """
    Récupère tous les statuts d'un compte publiés après 'start_date_utc'
    en utilisant la pagination (max_id).
    """
    url = f"https://{instance}/api/v1/accounts/{account_id}/statuses"
    
    headers = {
        'Authorization': f'Bearer {api_token}'
    }
    
    all_statuses = []
    max_id = None
    keep_paginating = True
    
    print(f"Démarrage de la récupération paginée (Limite/page: {limit})...")

    while keep_paginating:
        params = {
            'limit': limit,
            'exclude_replies': True,
            'exclude_reblogs': True
        }
        if max_id:
            params['max_id'] = max_id
        
        try:
            response = requests.get(url, params=params, headers=headers) 
            response.raise_for_status()
            current_statuses = response.json()
            
            if not current_statuses:
                print("Fin de la pagination (aucun nouveau statut retourné).")
                break
                
            last_status_id = None
            
            for status in current_statuses:
                last_status_id = status.get('id')
                status_created_at_str = status.get('created_at')
                
                # Conversion de la date pour le filtrage
                status_date_utc = datetime.strptime(status_created_at_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
                
                if status_date_utc >= start_date_utc:
                    # Le statut est récent : on l'ajoute et on continue
                    all_statuses.append(status)
                else:
                    # Le statut est trop ancien : on arrête la pagination
                    print(f"Statut {last_status_id} est trop ancien. Arrêt de la pagination.")
                    keep_paginating = False
                    break # Sort de la boucle 'for'
            
            # Mise à jour de max_id pour la prochaine itération (le dernier post récupéré)
            if keep_paginating and last_status_id:
                max_id = last_status_id
                print(f"Page récupérée. Poursuite avec max_id={max_id}. (Posts totaux: {len(all_statuses)})")
            
            # Petite pause pour respecter le débit de l'API
            time.sleep(1) 
            
        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des statuts : {e}")
            print("Vérifiez la validité du token et de l'instance.")
            break

    return all_statuses

# --- Préparation des Données JSON ---
def prepare_status_for_json(status_data):
    """Extrait et nettoie les champs pertinents pour l'affichage Jekyll."""
    
    raw_content = status_data.get('content', '')
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    clean_content_raw_text = h.handle(raw_content).strip()

    content_text_only = re.sub(URL_REGEX, '', clean_content_raw_text).strip()

    pub_date_str = status_data.get('created_at')
    pub_date_utc = datetime.strptime(pub_date_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.utc)
    pub_date_local = pub_date_utc.astimezone(TARGET_TIMEZONE)
    jekyll_date = pub_date_local.strftime('%Y-%m-%dT%H:%M:%S%z') 

    # Traitement des cartes (liens externes)
    card = status_data.get('card')
    card_data = {}
    if card:
        # CONSERVATION DU LIEN SOURCE
        card_data['url'] = card.get('url') 
        card_data['title'] = card.get('title')
        card_data['description'] = card.get('description')
        card_data['image'] = card.get('image')
        
        if card.get('url'):
            try:
                parsed_url = urlparse(card['url'])
                card_data['domaine'] = parsed_url.netloc
            except Exception as e:
                print(f"Avertissement : Impossible de parser le domaine pour {card['url']} (carte): {e}")

    # Construction de l'objet de données
    return {
        'id': status_data.get('id'),
        'url': status_data.get('url'),
        'date': jekyll_date,
        'text': content_text_only,
        'html_content': raw_content, 
        'card': card_data if card else None,
        'favourites_count': status_data.get('favourites_count', 0),
    }

# --- Fonction de Sauvegarde JSON ---
def save_data_to_json(data_list):
    """Sauvegarde la liste des posts dans le fichier JSON."""
    clean_data_directory(DATA_DIR)
    
    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump({'posts': data_list}, f, ensure_ascii=False, indent=2) 
        
        print(f"✅ Succès : {len(data_list)} posts sauvegardés dans {OUTPUT_JSON_FILE}")
        return True
    except IOError as e:
        print(f"❌ Erreur lors de l'écriture du fichier JSON '{OUTPUT_JSON_FILE}': {e}")
        return False


# --- Exécution Principale ---
if __name__ == "__main__":
    print("--- Démarrage du processus de récupération des posts Mastodon (JSON) ---")
    
    if not MASTODON_USERNAME or not MASTODON_API_TOKEN:
        print("Erreur: Les variables MASTODON_USERNAME ou MASTODON_PASSWORD (token d'API) ne sont pas définies.")
        exit(1)

    all_processed_posts = []
    
    account_id = get_account_id(MASTODON_INSTANCE, MASTODON_USERNAME)

    if account_id:
        print(f"ID numérique pour '{MASTODON_USERNAME}' : {account_id}")
        
        now_utc = datetime.now(timezone.utc)
        
        # Définition de la date de début du filtre (7 jours)
        start_date_utc = now_utc - timedelta(days=DAYS_TO_FETCH)
        start_date_utc = datetime(start_date_utc.year, start_date_utc.month, start_date_utc.day, 0, 0, 0, tzinfo=timezone.utc)
        
        print(f"Récupération des posts publiés depuis : {start_date_utc.astimezone(TARGET_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S %Z')} (soit les {DAYS_TO_FETCH} derniers jours)")

        # Appel de la fonction paginée qui filtre par date
        statuses = get_account_statuses(
            MASTODON_INSTANCE, 
            account_id, 
            MASTODON_API_TOKEN, 
            start_date_utc, 
            limit=API_FETCH_LIMIT
        ) 
        
        if statuses:
            print(f"Traitement de {len(statuses)} posts trouvés dans les {DAYS_TO_FETCH} derniers jours.")
            
            # Tri final par sécurité, bien que l'API les retourne déjà triés.
            statuses.sort(key=lambda x: x.get('created_at'), reverse=True) 

            for status in statuses:
                # Tous les posts ici sont déjà filtrés par date et par type (pas de réponse/repost)
                processed_post = prepare_status_for_json(status)
                all_processed_posts.append(processed_post)
                
            # Sauvegarde finale
            save_data_to_json(all_processed_posts)

        else:
            print(f"Aucun statut trouvé pour le profil '{MASTODON_USERNAME}' durant la période spécifiée.")
    else:
        print(f"Impossible de trouver l'ID numérique pour le profil '{MASTODON_USERNAME}'.")
    
    print("--- Processus Mastodon terminé ---")