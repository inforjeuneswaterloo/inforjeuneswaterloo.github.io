import datetime
import os
import yaml
from atproto import Client, models
import urllib.parse
# Removed: import re # Plus nécessaire si apply_facets_to_text est supprimé
import traceback

# --- Configuration ---
BLUESKY_USERNAME = os.environ.get("BLUESKY_USERNAME")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD")
JEKYLL_POSTS_DIR = "_news"

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
    Nettoie le texte pour l'utiliser comme nom de fichier.
    Remplace les caractères non valides par un tiret et gère les multiples tirets.
    """
    text = text.lower()
    text = text.replace(" ", "-")
    text = "".join(c if c.isalnum() or c == "-" else "-" for c in text)
    text = "-".join(filter(None, text.split('-'))) # Gère les multiples tirets et les tirets en début/fin
    return text

def get_external_link_title(post_embed):
    """
    Extrait le titre d'un lien externe partagé dans un post Bluesky.
    Retourne le titre ou None si aucun lien externe ou titre n'est trouvé.
    Gère les différentes structures d'embed.
    """
    if post_embed:
        # Cas 1: L'embed est directement un lien externe (app.bsky.embed.external)
        if isinstance(post_embed, models.AppBskyEmbedExternal.View):
            return post_embed.external.title
        # Cas 2: L'embed est un enregistrement avec média, et le média est un lien externe
        elif isinstance(post_embed, models.AppBskyEmbedRecordWithMedia.View) and \
             isinstance(post_embed.media, models.AppBskyEmbedExternal.View):
            return post_embed.media.external.title
        # Cas 3: L'embed est un enregistrement (par exemple, un post cité) qui contient lui-même des embeds
        elif isinstance(post_embed, models.AppBskyEmbedRecord.View) and \
             isinstance(post_embed.record, models.AppBskyEmbedRecord.ViewRecord) and \
             hasattr(post_embed.record, 'embeds') and post_embed.record.embeds:
            # On parcourt les embeds de l'enregistrement pour trouver un lien externe
            for embed_item in post_embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View):
                    return embed_item.external.title
    return None


def extract_external_uri_from_embed(post_embed):
    """
    Tente d'extraire l'URI d'un lien externe depuis un embed.
    Utile pour la suppression du texte du post.
    """
    if post_embed:
        if isinstance(post_embed, models.AppBskyEmbedExternal.View):
            return post_embed.external.uri
        elif isinstance(post_embed, models.AppBskyEmbedRecordWithMedia.View) and \
             isinstance(post_embed.media, models.AppBskyEmbedExternal.View):
            return post_embed.media.external.uri
        elif isinstance(post_embed, models.AppBskyEmbedRecord.View) and \
             isinstance(post_embed.record, models.AppBskyEmbedRecord.ViewRecord) and \
             hasattr(post_embed.record, 'embeds') and post_embed.record.embeds:
            for embed_item in post_embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View):
                    return embed_item.external.uri
    return None

# Removed: def apply_facets_to_text(text, facets): (This function is no longer present)


def generate_post_title(post_text, post_date, post_embed=None):
    """
    Génère un titre pour un post Bluesky.
    Priorité: 1. Titre de lien externe, 2. Première ligne du texte, 3. Date et heure du post.
    """
    # 1. Tente d'extraire le titre d'un lien externe partagé
    external_title = get_external_link_title(post_embed)
    if external_title:
        if len(external_title) > 150:
            return external_title[:147] + "..."
        return external_title

    # 2. Si pas de lien externe, prend la première ligne du texte du post
    if post_text:
        # Removed: re.sub(r'\[(.*?)\]\(.*?\)', r'\1', ...) for cleaning Markdown links
        first_line = post_text.splitlines()[0].strip() 
        if first_line:
            if len(first_line) > 100:
                return first_line[:97] + "..."
            return first_line
    
    # 3. Si texte vide ou première ligne vide, utilise la date et l'heure
    return f"Post du {post_date.strftime('%Y-%m-%d %H:%M')}"


def format_post_data(post):
    """
    Formate les données d'un post individuel pour être stockées dans le Front Matter YAML.
    Gère le texte, l'auteur, la date, les images, les posts cités et les liens externes avec thumbnails.
    """
    author_handle = post.author.handle if hasattr(post.author, 'handle') else 'unknown'
    created_at = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
    
    # Restored to original text extraction, no facet processing
    text = post.record.text if hasattr(post.record, 'text') else ''
    
    post_url = convert_at_uri_to_https_url(post.uri, author_handle)

    external_uri_in_text = extract_external_uri_from_embed(post.embed)
    if external_uri_in_text and external_uri_in_text in text:
        text = text.replace(external_uri_in_text, "").strip()
        text = text.strip()


    post_title = generate_post_title(text, created_at, post.embed)

    images = []
    if post.embed:
        if isinstance(post.embed, models.AppBskyEmbedImages.View):
            if hasattr(post.embed, 'images') and post.embed.images:
                for img in post.embed.images:
                    images.append({
                        'url': img.fullsize,
                        'alt': img.alt if hasattr(img, 'alt') else f"Image par {author_handle}",
                        'thumb': img.thumb if hasattr(img, 'thumb') else None
                    })
        elif isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View):
            if hasattr(post.embed, 'media') and isinstance(post.embed.media, models.AppBskyEmbedImages.View):
                if hasattr(post.embed.media, 'images') and post.embed.media.images:
                    for img in post.embed.media.images:
                        images.append({
                            'url': img.fullsize,
                            'alt': img.alt if hasattr(img, 'alt') else f"Image par {author_handle}",
                            'thumb': img.thumb if hasattr(img, 'thumb') else None
                        })

    quoted_post = None
    if post.embed:
        if isinstance(post.embed, models.AppBskyEmbedRecord.View):
            if hasattr(post.embed, 'record') and isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
                quoted_post_data = post.embed.record
                quoted_post_handle = quoted_post_data.author.handle if hasattr(quoted_post_data.author, 'handle') else 'unknown'
                quoted_post_text = quoted_post_data.value.text if hasattr(quoted_post_data.value, 'text') else ''
                quoted_post_url = convert_at_uri_to_https_url(quoted_post_data.uri, quoted_post_handle)
                
                quoted_post = {
                    'author_handle': quoted_post_handle,
                    'text': quoted_post_text,
                    'url': quoted_post_url
                }
        elif isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View):
            if hasattr(post.embed, 'record') and isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
                quoted_post_data = post.embed.record
                quoted_post_handle = quoted_post_data.author.handle if hasattr(quoted_post_data.author, 'handle') else 'unknown'
                quoted_post_text = quoted_post_data.value.text if hasattr(quoted_post_data.value, 'text') else ''
                quoted_post_url = convert_at_uri_to_https_url(quoted_post_data.uri, quoted_post_handle)
                
                quoted_post = {
                    'author_handle': quoted_post_handle,
                    'text': quoted_post_text,
                    'url': quoted_post_url
                }

    external_link = None
    if post.embed:
        if isinstance(post.embed, models.AppBskyEmbedExternal.View):
            external_link_uri = post.embed.external.uri
            external_link = {
                'uri': external_link_uri,
                'title': post.embed.external.title if hasattr(post.embed.external, 'title') else None,
                'description': post.embed.external.description if hasattr(post.embed.external, 'description') else None,
                'thumb': post.embed.external.thumb if hasattr(post.embed.external, 'thumb') else None
            }
        elif isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View) and \
             isinstance(post.embed.media, models.AppBskyEmbedExternal.View):
            external_link_uri = post.embed.media.external.uri
            external_link = {
                'uri': external_link_uri,
                'title': post.embed.media.external.title if hasattr(post.embed.media.external, 'title') else None,
                'description': post.embed.media.external.description if hasattr(post.embed.media.external, 'description') else None,
                'thumb': post.embed.media.external.thumb if hasattr(post.embed.media.external, 'thumb') else None
            }
        elif isinstance(post.embed, models.AppBskyEmbedRecord.View) and \
             isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord) and \
             hasattr(post.embed.record, 'embeds') and post.embed.record.embeds:
            for embed_item in post.embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View):
                    external_link = {
                        'uri': embed_item.external.uri,
                        'title': embed_item.external.title if hasattr(embed_item.external, 'title') else None,
                        'description': embed_item.external.description if hasattr(embed_item.external, 'description') else None,
                        'thumb': embed_item.external.thumb if hasattr(embed_item.external, 'thumb') else None
                    }
                    break

    return {
        'title': post_title,
        'author': author_handle,
        'date': created_at.isoformat(),
        'text': text,
        'url': post_url,
        'images': images,
        'quoted_post': quoted_post,
        'external_link': external_link
    }

def process_thread_recursive(thread_view, level=0):
    """
    Traite un thread de manière récursive et génère une structure de données (liste de dictionnaires)
    pour le Front Matter de Jekyll, en aplatissant les réponses pour la grille.
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
    Chaque fichier .md est nommé d'après la date et la rkey du post racine pour une unicité.
    """
    authenticate_bluesky()

    print(f"Fetching your Bluesky feed ({BLUESKY_USERNAME}) to find thread roots...")
    feed_response = client.app.bsky.feed.get_author_feed({'actor': BLUESKY_USERNAME, 'limit': 50})

    processed_thread_uris = set()

    for feed_item in feed_response.feed:
        post = feed_item.post
        post_rkey = post.uri.split('/')[-1]

        if not post.record.reply and post.uri not in processed_thread_uris:
            print(f"Found potential thread root: {post.uri}")
            try:
                thread_response = client.app.bsky.feed.get_post_thread({'uri': post.uri, 'depth': 5})
                thread_view = thread_response.thread

                if thread_view and hasattr(thread_view, 'post') and thread_view.post and thread_view.post.uri == post.uri:
                    def mark_posts_in_thread_as_processed(t_view_node):
                        if hasattr(t_view_node, 'post') and t_view_node.post:
                            processed_thread_uris.add(t_view_node.post.uri)
                        if hasattr(t_view_node, 'replies') and t_view_node.replies:
                            for r_t_view_node in t_view_node.replies:
                                mark_posts_in_thread_as_processed(r_t_view_node)
                    mark_posts_in_thread_as_processed(thread_view)

                    thread_posts_data = process_thread_recursive(thread_view)

                    main_post_title = "Bluesky Thread"
                    main_post_description = ""
                    main_post_image = None
                    main_post_thumb = None
                    main_source_url = None
                    main_source_domain = None
                    
                    root_author_handle = thread_view.post.author.handle if hasattr(thread_view.post.author, 'handle') else None
                    
                    if thread_posts_data and len(thread_posts_data) > 0 and thread_posts_data[0]['is_root']:
                        main_post_title = thread_posts_data[0]['title']
                        main_post_description = thread_posts_data[0]['text']

                        root_bsky_post = thread_view.post
                        if hasattr(root_bsky_post, 'embed') and root_bsky_post.embed:
                            if isinstance(root_bsky_post.embed, models.AppBskyEmbedImages.View):
                                if hasattr(root_bsky_post.embed, 'images') and root_bsky_post.embed.images:
                                    main_post_image = root_bsky_post.embed.images[0].fullsize
                                    main_post_thumb = root_bsky_post.embed.images[0].thumb if hasattr(root_bsky_post.embed.images[0], 'thumb') else None
                            elif isinstance(root_bsky_post.embed, models.AppBskyEmbedRecordWithMedia.View):
                                if hasattr(root_bsky_post.embed, 'media') and isinstance(root_bsky_post.embed.media, models.AppBskyEmbedImages.View):
                                    if hasattr(root_bsky_post.embed.media, 'images') and root_bsky_post.embed.media.images:
                                        main_post_image = root_bsky_post.embed.media.images[0].fullsize
                                        main_post_thumb = root_bsky_post.embed.media.images[0].thumb if hasattr(root_bsky_post.embed.media.images[0], 'thumb') else None
                                elif hasattr(root_bsky_post.embed, 'media') and isinstance(root_bsky_post.embed.media, models.AppBskyEmbedExternal.View):
                                    main_source_url = root_bsky_post.embed.media.external.uri if hasattr(root_bsky_post.embed.media.external, 'uri') else None
                                    if main_source_url:
                                        parsed_url = urllib.parse.urlparse(main_source_url)
                                        main_source_domain = parsed_url.netloc
                                    if hasattr(root_bsky_post.embed.media.external, 'thumb') and root_bsky_post.embed.media.external.thumb:
                                        main_post_thumb = root_bsky_post.embed.media.external.thumb

                            elif isinstance(root_bsky_post.embed, models.AppBskyEmbedRecord.View):
                                if hasattr(root_bsky_post.embed, 'record') and isinstance(root_bsky_post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
                                    if hasattr(root_bsky_post.embed.record, 'embeds') and root_bsky_post.embed.record.embeds:
                                        for embed_item in root_bsky_post.embed.record.embeds:
                                            if isinstance(embed_item, models.AppBskyEmbedImages.View):
                                                if hasattr(embed_item, 'images') and embed_item.images:
                                                    main_post_image = embed_item.images[0].fullsize
                                                    main_post_thumb = embed_item.images[0].thumb if hasattr(embed_item.images[0], 'thumb') else None
                                                    break
                                            elif isinstance(embed_item, models.AppBskyEmbedExternal.View):
                                                if hasattr(embed_item.external, 'thumb') and embed_item.external.thumb:
                                                    main_post_thumb = embed_item.external.thumb
                                                main_source_url = embed_item.external.uri if hasattr(embed_item.external, 'uri') else None
                                                if main_source_url:
                                                    parsed_url = urllib.parse.urlparse(main_source_url)
                                                    main_source_domain = parsed_url.netloc
                                                break
                                            
                            elif isinstance(root_bsky_post.embed, models.AppBskyEmbedExternal.View):
                                main_source_url = root_bsky_post.embed.external.uri if hasattr(root_bsky_post.embed.external, 'uri') else None
                                if main_source_url:
                                    parsed_url = urllib.parse.urlparse(main_source_url)
                                    main_source_domain = parsed_url.netloc
                                if hasattr(root_bsky_post.embed.external, 'thumb') and root_bsky_post.embed.external.thumb:
                                    main_post_thumb = root_bsky_post.embed.external.thumb

                    else:
                        published_date_fallback = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                        main_post_title = generate_post_title(post.record.text, published_date_fallback, post.embed)
                        main_post_description = post.record.text

                    published_date = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                    
                    filename = f"{published_date.strftime('%Y-%m-%d')}-{post_rkey}.md"
                    filepath = os.path.join(JEKYLL_POSTS_DIR, filename)

                    if os.path.exists(filepath):
                        print(f"Skipping existing thread file: {filename}")
                        continue

                    print(f"Creating thread file: {filename}")

                    front_matter_data = {
                        'layout': 'bluesky_thread',
                        'title': main_post_title,
                        'description': main_post_description,
                        'date': published_date.isoformat(),
                        'categories': 'bluesky',
                        'tags': ['bluesky', 'thread', 'microblogging'],
                        'bluesky_thread_url': convert_at_uri_to_https_url(post.uri, root_author_handle),
                        'root': convert_at_uri_to_https_url(post.uri, root_author_handle),
                        'thread_posts': thread_posts_data
                    }
                    
                    if main_post_image:
                        front_matter_data['image'] = main_post_image
                    
                    if main_post_thumb:
                        front_matter_data['thumb'] = main_post_thumb
                    
                    if main_source_url:
                        front_matter_data['source_url'] = main_source_url
                    if main_source_domain:
                        front_matter_data['source_domain'] = main_source_domain


                    front_matter_str = yaml.dump(front_matter_data, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2,
                                                 width=float('inf'))

                    if front_matter_str.endswith('\n\n'):
                        front_matter_str = front_matter_str.strip() + '\n'


                    markdown_content = f"""---
{front_matter_str}---

Ce post contient un thread Bluesky synchronisé depuis mon compte @{BLUESKY_USERNAME}.
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