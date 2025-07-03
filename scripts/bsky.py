import datetime
import os
import yaml
from atproto import Client, models
import urllib.parse
import re
import traceback
import requests

# --- Configuration ---

BLUESKY_USERNAME = os.environ.get("BLUESKY_USERNAME") # Nom d'utilisateur Bluesky (via Secrets)
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD") # Mot de passe d'application Bluesky (via Secrets)

JEKYLL_POSTS_DIR = "_news" # Dossier pour les posts Bluesky (collection _news)

# --- Initialisation du client Bluesky ---
client = Client()

# --- Helper Functions ---
def convert_at_uri_to_https_url(at_uri, author_handle=None):
    """
    Convertit une URI at:// (par exemple, at://did/collection/rkey)
    en une URL HTTPS lisible par le navigateur pour bsky.app.
    Nécessite le handle de l'auteur pour les posts, si disponible.
    """
    try:
        if not at_uri or not at_uri.startswith('at://'):
            return at_uri # Retourne l'URI originale si non valide ou non at://

        parts = at_uri.split('/')
        if len(parts) >= 5 and parts[0] == 'at:':
            did_or_handle_part = parts[2] # This could be a DID or a handle in some contexts
            collection = parts[3]
            rkey = parts[4]

            if collection == 'app.bsky.feed.post':
                # For posts, we prefer the handle. If not available, use the DID.
                if author_handle:
                    return f"https://bsky.app/profile/{author_handle}/post/{rkey}"
                else:
                    # Fallback to DID if handle is not provided/available
                    return f"https://bsky.app/profile/{did_or_handle_part}/post/{rkey}"
            elif collection == 'app.bsky.actor.profile':
                # Profiles are typically handled directly by DID or handle if resolved
                return f"https://bsky.app/profile/{did_or_handle_part}"
            # Add other collection types if needed
        return at_uri # Retourne l'URI originale si non convertible
    except Exception as e:
        print(f"Erreur de conversion URI '{at_uri}': {e}")
        traceback.print_exc() # Log full traceback for conversion errors
        return at_uri # Retourne l'URI originale en cas d'erreur


def authenticate_bluesky():
    """Authentifie le client Bluesky."""
    if not BLUESKY_USERNAME or not BLUESKY_APP_PASSWORD:
        print("Erreur: Les variables BLUESKY_USERNAME et BLUESKY_APP_PASSWORD ne sont pas définies.")
        print("Pour générer un mot de passe d'application: Bluesky -> Paramètres -> Advanced -> App Passwords.")
        exit(1)

    try:
        print("Authenticating with Bluesky...")
        client.login(BLUESKY_USERNAME, BLUESKY_APP_PASSWORD)
        print("Authentication successful.")
    except Exception as e:
        print(f"Authentication failed: {e}")
        print("Veuillez vous assurer que BLUESKY_USERNAME et BLUESKY_APP_PASSWORD sont corrects ou essayez de régénérer le mot de passe d'application.")
        traceback.print_exc() # Log full traceback for authentication errors
        exit(1)

def sanitize_filename(text):
    """
    Nettoyage du texte pour l'utiliser comme nom de fichier.
    """
    text = text.lower()
    text = text.replace(" ", "-")
    text = "".join(c if c.isalnum() or c == "-" else "-" for c in text)
    text = "-".join(filter(None, text.split('-'))) # Gère les multiples tirets et les tirets en début/fin
    return text

# La fonction get_bluesky_oembed_html n'est plus présente car l'API Bluesky ne la gère pas publiquement.


# --- Fonctions d'extraction de données depuis les objets Bluesky ---
def get_external_link_title(post_embed):
    """Extrait le titre d'un lien externe d'un post Bluesky embed."""
    if post_embed:
        if isinstance(post_embed, models.AppBskyEmbedExternal.View): return post_embed.external.title
        elif isinstance(post_embed, models.AppBskyEmbedRecordWithMedia.View) and isinstance(post_embed.media, models.AppBskyEmbedExternal.View): return post_embed.media.external.title
        elif isinstance(post_embed, models.AppBskyEmbedRecord.View) and isinstance(post_embed.record, models.AppBskyEmbedRecord.ViewRecord) and hasattr(post_embed.record, 'embeds') and post_embed.record.embeds:
            for embed_item in post_embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View): return embed_item.external.title
    return None

def extract_external_uri_from_embed(post_embed):
    """Extrait l'URI d'un lien externe d'un post Bluesky embed."""
    if post_embed:
        if isinstance(post_embed, models.AppBskyEmbedExternal.View): return post_embed.external.uri
        elif isinstance(post_embed, models.AppBskyEmbedRecordWithMedia.View) and isinstance(post_embed.media, models.AppBskyEmbedExternal.View): return post_embed.media.external.uri
        elif isinstance(post_embed, models.AppBskyEmbedRecord.View) and isinstance(post_embed.record, models.AppBskyEmbedRecord.ViewRecord) and hasattr(post_embed.record, 'embeds') and post_embed.record.embeds:
            for embed_item in post_embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View): return embed_item.external.uri
    return None

def generate_post_title(post_text, post_date, post_embed=None):
    """
    Génère un titre pour un post Bluesky.
    Priorité: 1. Titre de lien externe, 2. Première ligne du texte, 3. Date et heure du post.
    """
    external_title = get_external_link_title(post_embed)
    if external_title:
        return (external_title[:147] + "...") if len(external_title) > 150 else external_title
    if post_text:
        first_line = post_text.splitlines()[0].strip()
        if first_line:
            return (first_line[:97] + "...") if len(first_line) > 100 else first_line
    return f"Post du {post_date.strftime('%Y-%m-%d %H:%M')}"

def format_post_data(post):
    """
    Formate les données d'un post individuel (racine ou réponse) pour être stockées dans le Front Matter YAML.
    """
    author_handle = post.author.handle if hasattr(post.author, 'handle') else 'unknown'
    created_at = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
    text = post.record.text if hasattr(post.record, 'text') else ''
    post_url = convert_at_uri_to_https_url(post.uri, author_handle)
    
    # Supprime l'URI externe du texte si elle y est présente (pour le texte brut du post)
    external_uri_in_text = extract_external_uri_from_embed(post.embed)
    if external_uri_in_text and external_uri_in_text in text:
        text = text.replace(external_uri_in_text, "").strip()

    post_title = generate_post_title(text, created_at, post.embed)

    # Images attachées au post
    images = []
    if post.embed and isinstance(post.embed, models.AppBskyEmbedImages.View) and hasattr(post.embed, 'images'):
        for img in post.embed.images:
            images.append({'url': img.fullsize, 'alt': img.alt or f"Image par {author_handle}", 'thumb': img.thumb})
    elif post.embed and isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View) and hasattr(post.embed.media, 'images') and isinstance(post.embed.media, models.AppBskyEmbedImages.View):
        for img in post.embed.media.images:
            images.append({'url': img.fullsize, 'alt': img.alt or f"Image par {author_handle}", 'thumb': img.thumb})

    # Post cité dans l'embed
    quoted_post_data = None
    if post.embed and isinstance(post.embed, models.AppBskyEmbedRecord.View) and hasattr(post.embed, 'record') and isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
        quoted_post_author = post.embed.record.author.handle if hasattr(post.embed.record.author, 'handle') else 'unknown'
        quoted_post_data = {
            'author_handle': quoted_post_author,
            'text': post.embed.record.value.text,
            'url': convert_at_uri_to_https_url(post.embed.record.uri, quoted_post_author)
        }
    elif post.embed and isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View) and hasattr(post.embed.record, 'record') and isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
        quoted_post_author = post.embed.record.author.handle if hasattr(post.embed.record.author, 'handle') else 'unknown'
        quoted_post_data = {
            'author_handle': quoted_post_author,
            'text': post.embed.record.value.text,
            'url': convert_at_uri_to_https_url(post.embed.record.uri, quoted_post_author)
        }

    # Lien externe dans l'embed
    external_link_data = None
    if post.embed and isinstance(post.embed, models.AppBskyEmbedExternal.View) and hasattr(post.embed, 'external'):
        external_link_data = {
            'uri': post.embed.external.uri,
            'title': post.embed.external.title,
            'description': post.embed.external.description,
            'thumb': post.embed.external.thumb
        }
    elif post.embed and isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View) and hasattr(post.embed.media, 'external') and isinstance(post.embed.media, models.AppBskyEmbedExternal.View):
        external_link_data = {
            'uri': post.embed.media.external.uri,
            'title': post.embed.media.external.title,
            'description': post.embed.media.external.description,
            'thumb': post.embed.media.external.thumb
        }

    return {
        'title': post_title,
        'author': author_handle,
        'date': created_at.isoformat(),
        'text': text, # Le texte nettoyé du post du thread
        'url': post_url,
        'images': images if images else None,
        'quoted_post': quoted_post_data,
        'external_link': external_link_data,
    }

def process_thread_recursive(thread_view, level=0):
    """
    Traite un thread de manière récursive, formatte chaque post et assigne son niveau.
    """
    thread_data_list = []

    if thread_view.post:
        post_author_handle = thread_view.post.author.handle if hasattr(thread_view.post.author, 'handle') else None
        post_data = format_post_data(thread_view.post)
        post_data['is_root'] = (level == 0)
        post_data['level'] = level
        thread_data_list.append(post_data)

    if hasattr(thread_view, 'replies') and thread_view.replies:
        for reply_thread_view in thread_view.replies:
            thread_data_list.extend(process_thread_recursive(reply_thread_view, level + 1))
    return thread_data_list

def fetch_and_create_threaded_posts():
    """
    Récupère les posts et threads depuis Bluesky et crée des fichiers Markdown pour Jekyll.
    """
    authenticate_bluesky()

    print(f"Fetching your Bluesky feed ({BLUESKY_USERNAME}) to find thread roots...")
    feed_response = client.app.bsky.feed.get_author_feed({'actor': BLUESKY_USERNAME, 'limit': 50})

    processed_thread_uris = set()

    for feed_item in feed_response.feed:
        post = feed_item.post
        post_rkey = post.uri.split('/')[-1]

        # Traite uniquement les posts racines qui n'ont pas déjà été traités dans un autre thread
        if not post.record.reply and post.uri not in processed_thread_uris:
            print(f"Found potential thread root: {post.uri}")
            try:
                # Récupère le thread complet jusqu'à une certaine profondeur
                thread_response = client.app.bsky.feed.get_post_thread({'uri': post.uri, 'depth': 5})
                thread_view = thread_response.thread

                # S'assure que le post racine correspond bien et marque tous les posts du thread comme traités
                if thread_view and hasattr(thread_view, 'post') and thread_view.post and thread_view.post.uri == post.uri:
                    def mark_posts_in_thread_as_processed(t_view_node):
                        if hasattr(t_view_node, 'post') and t_view_node.post:
                            processed_thread_uris.add(t_view_node.post.uri)
                        if hasattr(t_view_node, 'replies') and t_view_node.replies:
                            for r_t_view_node in t_view_node.replies:
                                mark_posts_in_thread_as_processed(r_t_view_node)
                    mark_posts_in_thread_as_processed(thread_view)

                    thread_posts_data = process_thread_recursive(thread_view) # Les données complètes du thread

                    # --- Préparation du Front Matter ---
                    # Le titre du post principal
                    main_post_title = "Bluesky Thread"
                    root_bsky_post = thread_view.post
                    if hasattr(root_bsky_post.record, 'text'):
                        main_post_title = generate_post_title(root_bsky_post.record.text, datetime.datetime.fromisoformat(root_bsky_post.record.created_at.replace('Z', '+00:00')), root_bsky_post.embed)
                    
                    # URL du post racine Bluesky
                    root_author_handle = thread_view.post.author.handle if hasattr(thread_view.post.author, 'handle') else None
                    root_post_url = convert_at_uri_to_https_url(root_bsky_post.uri, root_author_handle)

                    # Date de publication du post racine
                    published_date = datetime.datetime.fromisoformat(root_bsky_post.record.created_at.replace('Z', '+00:00'))
                    
                    # Nom de fichier basé sur la date et le rkey
                    filename = f"{published_date.strftime('%Y-%m-%d')}-{post_rkey}.md"
                    filepath = os.path.join(JEKYLL_POSTS_DIR, filename)

                    if os.path.exists(filepath):
                        print(f"Skipping existing thread file: {filename}")
                        continue

                    print(f"Creating thread file: {filename}")

                    # Front Matter du post Jekyll
                    front_matter_data = {
                        'layout': 'bluesky_thread', # Layout spécifique pour l'affichage des threads
                        'title': main_post_title,
                        'date': published_date.isoformat(),
                        'categories': 'bluesky',
                        'tags': ['bluesky', 'thread', 'microblogging'],
                        'bluesky_thread_url': root_post_url, # URL du post racine Bluesky
                        'thread_posts': thread_posts_data # LES DONNÉES COMPLÈTES DU THREAD SONT STOCKÉES ICI
                    }
                    
                    # Ajout optionnel d'autres métadonnées d'image/lien racine si présentes
                    if hasattr(root_bsky_post, 'embed'):
                        # Logique pour récupérer image/thumb/source_url/source_domain du post racine
                        # et les ajouter au FM si non-None.
                        # Cette logique est étendue et peut être simplifiée si vous voulez un FM plus strict.
                        if isinstance(root_bsky_post.embed, models.AppBskyEmbedImages.View) and root_bsky_post.embed.images:
                            front_matter_data['image'] = root_bsky_post.embed.images[0].fullsize
                            front_matter_data['thumb'] = root_bsky_post.embed.images[0].thumb
                        elif isinstance(root_bsky_post.embed, models.AppBskyEmbedRecordWithMedia.View) and hasattr(root_bsky_post.embed, 'media'):
                            if isinstance(root_bsky_post.embed.media, models.AppBskyEmbedImages.View) and root_bsky_post.embed.media.images:
                                front_matter_data['image'] = root_bsky_post.embed.media.images[0].fullsize
                                front_matter_data['thumb'] = root_bsky_post.embed.media.images[0].thumb
                            elif isinstance(root_bsky_post.embed.media, models.AppBskyEmbedExternal.View) and hasattr(root_bsky_post.embed.media, 'external'):
                                front_matter_data['source_url'] = root_bsky_post.embed.media.external.uri
                                if hasattr(root_bsky_post.embed.media.external, 'thumb'): front_matter_data['thumb'] = root_bsky_post.embed.media.external.thumb
                                if hasattr(root_bsky_post.embed.media.external, 'title') and root_bsky_post.embed.media.external.uri:
                                    parsed_url = urllib.parse.urlparse(root_bsky_post.embed.media.external.uri)
                                    front_matter_data['source_domain'] = parsed_url.netloc

                        elif isinstance(root_bsky_post.embed, models.AppBskyEmbedExternal.View) and hasattr(root_bsky_post.embed, 'external'):
                            front_matter_data['source_url'] = root_bsky_post.embed.external.uri
                            if hasattr(root_bsky_post.embed.external, 'thumb'): front_matter_data['thumb'] = root_bsky_post.embed.external.thumb
                            if hasattr(root_bsky_post.embed.external, 'title') and root_bsky_post.embed.external.uri:
                                parsed_url = urllib.parse.urlparse(root_bsky_post.embed.external.uri)
                                front_matter_data['source_domain'] = parsed_url.netloc


                    front_matter_str = yaml.dump(front_matter_data, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2, width=float('inf'))

                    if front_matter_str.endswith('\n\n'):
                        front_matter_str = front_matter_str.strip() + '\n'

                    # --- Construction du corps du Markdown (texte brut du post racine) ---
                    # Le corps du Markdown contient le texte du post racine (nettoyé des liens).
                    # Le layout Jekyll devra ensuite afficher le thread complet en bouclant sur thread_posts.
                    markdown_content = f"""---
{front_matter_str}---

{root_bsky_post.record.text}
"""
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                else:
                    print(f"Post {post.uri} is a reply or thread structure not as expected, skipping as root.")
            except Exception as e:
                print(f"Error processing thread for {post.uri}: {e}")
                traceback.print_exc()

    print("Done creating Jekyll posts from Bluesky threads.")

if __name__ == "__main__":
    if not os.path.exists(JEKYLL_POSTS_DIR):
        os.makedirs(JEKYLL_POSTS_DIR)
        print(f"Created directory: {JEKYLL_POSTS_DIR}")

    fetch_and_create_threaded_posts()