import requests
import json
import os
import pytz
import re

# --- Configuration Globale (Lue depuis GitHub Actions Secrets/ENV) ---
USERNAME = os.environ.get("BLUESKY_USERNAME")
PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD") 
BLUESKY_DID = os.environ.get("BSKY_DID_PLC") # Utilisé comme identifiant de l'auteur

# Configuration du fichier de sortie et du filtre
DATA_DIR = "_data"
TARGET_TAG = "yotm" # <--- TAG CIBLE
# Fichier 1 : Le fichier filtré (nom basé sur le tag)
OUTPUT_FILTERED_FILE = os.path.join(DATA_DIR, f"bluesky_{TARGET_TAG}_posts.json") 
# Fichier 2 : Le fichier de toutes les données
OUTPUT_ALL_FILE = os.path.join(DATA_DIR, "bluesky_posts.json")
# [AJOUT] Fichier 3 : Le fichier des posts épinglés
OUTPUT_PINNED_FILE = os.path.join(DATA_DIR, "bsky_posts_pinned.json") # <--- NOUVEAU FICHIER CIBLE
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

# [NOUVELLE FONCTION]
def get_pinned_post_uri(session, did):
    """Récupère l'URI (at://...) du post épinglé d'un utilisateur depuis son profil."""
    profile_url = f"{API_PDS}/xrpc/app.bsky.actor.getProfile?actor={did}"
    try:
        response = session.get(profile_url)
        response.raise_for_status()
        profile_data = response.json()
        # Le champ 'pinnedPost' contient l'URI du post épinglé
        return profile_data.get('pinnedPost') 
    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur lors de la récupération du profil pour le post épinglé : {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur inattendue lors de la récupération du post épinglé : {e}")
        return None

# --- Fonction Principale ---
def fetch_bluesky_feed():
    """Authentifie, récupère le flux, filtre par tag, recherche le post épinglé et sauvegarde les trois fichiers."""
    
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

        # [AJOUT] 2. Récupération de l'URI du post épinglé AVANT d'appeler le flux
        pinned_post_uri = get_pinned_post_uri(session, BLUESKY_DID)
        if pinned_post_uri:
            print(f"✅ URI du post épinglé trouvé : {pinned_post_uri}")
        else:
            # S'il y a une erreur ou aucun post épinglé, on continue sans cette fonctionnalité
            print("ℹ️ Aucun post épinglé trouvé ou erreur lors de la récupération.")
        
        # 3. Appel API du flux
        feed_response = session.get(FEED_URL, headers=headers)
        feed_response.raise_for_status()
        data = feed_response.json()
        
        all_feed_items = data.get('feed', [])
        
        # --- Préparation des listes de sortie ---
        # [AJOUT] Liste pour les posts épinglés
        pinned_posts = [] 
        
        # On extrait seulement le 'post' de chaque 'item' pour simplifier le JSON de sortie
        all_posts_data = [item.get('post') for item in all_feed_items if item.get('post')]
        # --- Sauvegarde du Fichier 1 : TOUTES les données brutes ---
        save_data_to_json(all_posts_data, OUTPUT_ALL_FILE)


        # --- Traitement pour le Fichier 2 (filtré par tag) et Fichier 3 (épinglé) ---
        yotm_posts = [] 

        for item in all_feed_items:
            post = item.get('post')
            
            # FILTRAGE 1 : Exclure les Reposts et les Réponses
            if item.get('reason') or (post and post.get('record', {}).get('reply')):
                continue 
            
            if post:
                
                # [AJOUT] FILTRE 2 : Vérification du statut ÉPINGLÉ
                is_pinned = False
                if pinned_post_uri and post.get('uri') == pinned_post_uri:
                    # Traitement du post épinglé pour cohérence
                    post_text = post['record']['text']
                    cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                    post['record']['text'] = cleaned_text 
                    post['image_url'] = get_post_image_url(post)
                    
                    pinned_posts.append(post)
                    is_pinned = True
                    # On continue la boucle pour que le post épinglé puisse également être filtré par tag s'il le possède
                
                # FILTRAGE 3 (Ancien FILTRE 2) : Vérification du Tag Cible
                if not post_has_tag(post, TARGET_TAG):
                    # Si le post n'est ni épinglé, ni le tag cible, on passe au suivant
                    if not is_pinned:
                        continue 
                    else:
                        # Si le post est épinglé, on l'a déjà traité dans 'pinned_posts', on passe au suivant
                        continue

                # --- Traitement des posts VALIDES ET FILTRÉS (par tag) ---
                
                # Nettoyage du texte (suppression des URLs)
                post_text = post['record']['text']
                cleaned_text = re.sub(URL_REGEX, '', post_text, flags=re.IGNORECASE).strip()
                post['record']['text'] = cleaned_text 

                # Ajout de l'URL de l'image simplifiée
                post['image_url'] = get_post_image_url(post)
                
                # Ajout à la liste finale (yotm_posts)
                yotm_posts.append(post)

        # 4. Sauvegarde finale du Fichier 2 : Le flux filtré (par tag)
        save_data_to_json(yotm_posts, OUTPUT_FILTERED_FILE)
        
        # [AJOUT] 5. Sauvegarde finale du Fichier 3 : Les posts épinglés
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