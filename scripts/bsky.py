from atproto import Client, models
import json
import os

# --- Vos configurations ---
TARGET_BLUESKY_HANDLE = 'inforjeuneswaterloo.be' # Votre handle correct
DATA_DIR = '_data'
OUTPUT_FILE = os.path.join(DATA_DIR, 'bluesky_timeline.json') 

# Variables d'environnement pour l'authentification
BSKY_USERNAME = os.getenv('BLUESKY_USERNAME')
BSKY_APP_PASSWORD = os.getenv('BLUESKY_APP_PASSWORD')

def fetch_bluesky_timeline_for_authenticated_user():
    client = Client()

    if not BSKY_USERNAME or not BSKY_APP_PASSWORD:
        print("Erreur : Les variables d'environnement BLUESKY_USERNAME ou BLUESKY_APP_PASSWORD ne sont pas définies.")
        print("Veuillez les définir avant d'exécuter le script.")
        return

    try:
        print(f"Tentative de connexion avec l'utilisateur : {BSKY_USERNAME}")
        session = client.login(BSKY_USERNAME, BSKY_APP_PASSWORD)
        print("Connexion réussie à Bluesky.")
        
        my_handle = session.handle
        my_did = session.did
        print(f"Handle de l'utilisateur connecté : @{my_handle}")
        print(f"DID de l'utilisateur connecté : {my_did}")

        print(f"Récupération de la timeline pour l'utilisateur connecté (limit=10)")
        profile_response = client.app.bsky.actor.get_profile(params={'actor': TARGET_BLUESKY_HANDLE})
        did = profile_response.did
        
        feed = client.app.bsky.feed.get_author_feed(params={'actor': did, 'limit': 10}) # Récupère 10 derniers posts
        #feed = client.app.bsky.feed.get_timeline(params={'limit': 10}) 
        
        posts_data = []
        for item in feed.feed:
            post = item.post # C'est cet objet 'post' qui contient les vues des embeds
            author = post.author
            record = post.record # Le 'record' est la représentation interne du post, sans les URLs directes des images

            post_info = {
                'uri': post.uri,
                'cid': post.cid,
                'text': record.text,
                'created_at': record.created_at,
                'author_handle': author.handle,
                'author_display_name': author.display_name,
                'reply_count': post.reply_count,
                'repost_count': post.repost_count,
                'like_count': post.like_count,
                'embed': None # Initialisation pour éviter les erreurs si pas d'embed
            }
            
            # --- CORRECTION ICI : Accéder aux informations d'embed via 'post.embed' ---
            # 'post.embed' sera une vue de l'embed (ex: images, external, record)
            if post.embed:
                # Vérifiez si c'est un embed d'images
                if isinstance(post.embed, models.AppBskyEmbedImages.View):
                    images_data = []
                    # Itérer sur les objets image dans la vue de l'embed
                    for img_view in post.embed.images:
                        # Ces objets 'img_view' (models.AppBskyEmbedImages.View_Image)
                        # contiennent directement les URLs 'thumb' et 'fullsize'
                        images_data.append({
                            'thumb': img_view.thumb,
                            'fullsize': img_view.fullsize,
                            'alt': img_view.alt
                        })
                    post_info['embed'] = {'type': 'images', 'images': images_data}
                
                # --- Gérer d'autres types d'embeds si nécessaire (ex: liens externes) ---
                elif isinstance(post.embed, models.AppBskyEmbedExternal.View):
                    external_data = post.embed.external
                    post_info['embed'] = {
                        'type': 'external',
                        'uri': external_data.uri,
                        'title': external_data.title,
                        'description': external_data.description,
                        'thumb': external_data.thumb # Le thumb d'une carte de lien
                    }
                # Ajoutez d'autres cas (e.g., models.AppBskyEmbedRecord.View pour les reposts avec citation)
                # si vous voulez les gérer
            
            posts_data.append(post_info)

        output_data = {
            'authenticated_user_handle': my_handle,
            'authenticated_user_did': my_did,
            'posts': posts_data
        }

        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"Bluesky timeline data saved to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error fetching Bluesky timeline: {e}")

if __name__ == "__main__":
    fetch_bluesky_timeline_for_authenticated_user()