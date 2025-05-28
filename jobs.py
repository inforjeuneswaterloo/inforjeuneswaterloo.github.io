import datetime
import os
import yaml
from atproto import Client, models
import urllib.parse
import re

# --- Configuration ---
BLUESKY_USERNAME = "inforjeuneswaterloo.be"
BLUESKY_APP_PASSWORD = "46i7-h3ht-o2xg-6ryw"

JEKYLL_POSTS_DIR = "_news"

# --- Initialisation du client Bluesky ---
client = Client()

def authenticate_bluesky():
    """Authentifie le client Bluesky."""
    if not BLUESKY_USERNAME or not BLUESKY_APP_PASSWORD:
        print("Authenticating with Bluesky...")
        client.login(BLUESKY_USERNAME, BLUESKY_APP_PASSWORD)
        print("Authentication successful.")
    except Exception as e:
        print(f"Authentication failed: {e}")
        print("Please ensure BSKY_USERNAME and BSKY_APP_PASSWORD are correctly set.")
        print("To generate an app password: Bluesky -> Settings -> Advanced -> App Passwords.")
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

def apply_facets_to_text(text, facets):
    """
    Reconstruit le texte en insérant des liens Markdown pour les hashtags et les mentions.
    Les Bluesky URLs pour les hashtags sont basées sur la recherche.
    """
    if not facets:
        return text

    # Les facettes sont souvent dans l'ordre, mais il est plus sûr de les traiter
    # de la fin vers le début pour ne pas invalider les index.
    sorted_facets = sorted(facets, key=lambda f: f.index.byte_end, reverse=True)

    for facet in sorted_facets:
        start = facet.index.byte_start
        end = facet.index.byte_end
        
        # Vérifie que les index sont valides pour le texte
        if start < 0 or end > len(text) or start >= end:
            continue # Passe cette facette si les index sont invalides

        segment = text[start:end]

        # Itérer à travers les caractéristiques de la facette
        # CORRECTION: Accès direct à models.AppBskyRichtextFacet.Tag/Mention
        for feature in facet.features:
            if isinstance(feature, models.AppBskyRichtextFacet.Tag): # Correction ici: utilise isinstance et la classe directe
                # C'est un hashtag
                tag_name = segment.lstrip('#') # Retire le '#' pour la recherche
                hashtag_url = f"https://bsky.app/search?q=%23{urllib.parse.quote(tag_name)}"
                markdown_link = f"[#{tag_name}]({hashtag_url})"
                text = text[:start] + markdown_link + text[end:]
                break # Traite cette caractéristique et passe à la facette suivante
            elif isinstance(feature, models.AppBskyRichtextFacet.Mention): # Correction ici: utilise isinstance et la classe directe
                # C'est une mention (@handle)
                did = feature.did # Accès au DID depuis l'objet feature
                
                # Pour simplifier, on crée un lien vers le profil Bluesky avec le handle tel qu'il est.
                mention_handle_display = segment # Conserve le segment de texte original pour l'affichage
                profile_url = f"https://bsky.app/profile/{mention_handle_display.lstrip('@')}" # Lien vers le profil
                markdown_link = f"[{mention_handle_display}]({profile_url})"
                text = text[:start] + markdown_link + text[end:]
                break # Traite cette caractéristique et passe à la facette suivante
            # Les liens (models.AppBskyRichtextFacet.Link) pourraient être ajoutés ici si nécessaire
            # Mais Bluesky gère souvent les liens directs ou via les embeds.

    return text


def generate_post_title(post_text, post_date, post_embed=None):
    """
    Génère un titre pour un post Bluesky.
    Priorité: 1. Titre de lien externe, 2. Première ligne du texte, 3. Date et heure du post.
    """
    # 1. Tente d'extraire le titre d'un lien externe partagé
    external_title = get_external_link_title(post_embed)
    if external_title:
        # Limite la longueur pour un titre de page Jekyll, si nécessaire
        if len(external_title) > 150:
            return external_title[:147] + "..."
        return external_title

    # 2. Si pas de lien externe, prend la première ligne du texte du post
    if post_text:
        # Nettoie les liens Markdown pour la première ligne du titre
        cleaned_first_line = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', post_text.splitlines()[0].strip())
        if cleaned_first_line:
            # Limite à une longueur raisonnable pour un titre de carte/post, par exemple 100 caractères
            if len(cleaned_first_line) > 100:
                return cleaned_first_line[:97] + "..."
            return cleaned_first_line
    
    # 3. Si texte vide ou première ligne vide, utilise la date et l'heure
    return f"Post du {post_date.strftime('%Y-%m-%d %H:%M')}"


def format_post_data(post):
    """
    Formate les données d'un post individuel pour être stockées dans le Front Matter YAML.
    Gère le texte, l'auteur, la date, les images, les posts cités et les liens externes avec thumbnails.
    """
    author_handle = post.author.handle
    created_at = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
    
    # NOUVEAU : Appliquer les facettes pour créer les liens Markdown avant toute autre manipulation du texte
    text = apply_facets_to_text(post.record.text, post.record.facets)
    
    post_url = post.uri # L'AT-URI unique du post

    # Tentative de supprimer le lien externe du texte du post
    # (Maintenant que les facettes ont été traitées, cela supprime le lien brut, pas le Markdown)
    external_uri_in_text = extract_external_uri_from_embed(post.embed)
    if external_uri_in_text and external_uri_in_text in text:
        text = text.replace(external_uri_in_text, "").strip()
        # Supprimer les éventuels retours à la ligne ou espaces restants après la suppression
        text = text.strip()


    # Génère un titre pour ce post individuel (utilisé dans les cartes de la grille)
    post_title = generate_post_title(text, created_at, post.embed)

    images = []
    # Gère les images directement attachées au post
    if post.embed and isinstance(post.embed, models.AppBskyEmbedImages.View):
        for img in post.embed.images:
            images.append({
                'url': img.fullsize, # URL de l'image en taille réelle
                'alt': img.alt if hasattr(img, 'alt') else f"Image par {author_handle}",
                'thumb': img.thumb # Ajout de la miniature ici aussi pour chaque image individuelle
            })
    # Gère les images si le post est un record avec média (ex: post cité + image)
    elif post.embed and isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View):
         if post.embed.media and isinstance(post.embed.media, models.AppBskyEmbedImages.View):
             for img in post.embed.media.images:
                images.append({
                    'url': img.fullsize,
                    'alt': img.alt if hasattr(img, 'alt') else f"Image par {author_handle}",
                    'thumb': img.thumb # Ajout de la miniature ici aussi pour chaque image individuelle
                })

    quoted_post = None
    # Gère les posts cités
    if post.embed and isinstance(post.embed, models.AppBskyEmbedRecord.View):
        quoted_post = {
            'author_handle': post.embed.record.author.handle,
            'text': post.embed.record.value.text,
            'url': post.embed.record.uri
        }
    # Gère les posts cités avec média
    elif post.embed and isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View):
        if post.embed.record and isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord):
            quoted_post = {
                'author_handle': post.embed.record.author.handle,
                'text': post.embed.record.value.text,
                'url': post.embed.record.uri
            }

    external_link = None
    # Gère les liens externes et extrait leur aperçu (thumbnail)
    if post.embed:
        if isinstance(post.embed, models.AppBskyEmbedExternal.View):
            external_link = {
                'uri': post.embed.external.uri,
                'title': post.embed.external.title,
                'description': post.embed.external.description,
                'thumb': post.embed.external.thumb # URL de la miniature de l'article externe
            }
        elif isinstance(post.embed, models.AppBskyEmbedRecordWithMedia.View) and \
             isinstance(post.embed.media, models.AppBskyEmbedExternal.View):
            external_link = {
                'uri': post.embed.media.external.uri,
                'title': post.embed.media.external.title,
                'description': post.embed.media.external.description,
                'thumb': post.embed.media.external.thumb
            }
        elif isinstance(post.embed, models.AppBskyEmbedRecord.View) and \
             isinstance(post.embed.record, models.AppBskyEmbedRecord.ViewRecord) and \
             hasattr(post.embed.record, 'embeds') and post.embed.record.embeds:
            for embed_item in post.embed.record.embeds:
                if isinstance(embed_item, models.AppBskyEmbedExternal.View):
                    external_link = {
                        'uri': embed_item.external.uri,
                        'title': embed_item.external.title,
                        'description': embed_item.external.description,
                        'thumb': embed_item.external.thumb
                    }
                    break # On prend le premier lien externe trouvé et on s'arrête

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
        post_data = format_post_data(thread_view.post)
        post_data['is_root'] = (level == 0) # Marque le post racine
        post_data['level'] = level # Niveau d'imbrication dans le thread (0 pour le racine)
        thread_data_list.append(post_data)

    if thread_view.replies:
        for reply_thread_view in thread_view.replies:
            # Appel récursif pour traiter les réponses imbriquées
            thread_data_list.extend(process_thread_recursive(reply_thread_view, level + 1))
    return thread_data_list

def fetch_and_create_threaded_posts():
    """
    Récupère les posts et threads depuis Bluesky et crée des fichiers Markdown pour Jekyll.
    Chaque fichier .md est nommé d'après la date et la rkey du post racine pour une unicité.
    """
    authenticate_bluesky()

    print(f"Fetching your Bluesky feed ({BLUESKY_USERNAME}) to find thread roots...")
    # Récupère les 50 derniers posts du feed de l'utilisateur. Ajustez 'limit' si besoin.
    feed_response = client.app.bsky.feed.get_author_feed({'actor': BLUESKY_USERNAME, 'limit': 50})

    # Set pour garder une trace des URIs de posts déjà traités, afin d'éviter les doublons.
    processed_thread_uris = set()

    for feed_item in feed_response.feed:
        post = feed_item.post
        # Extraire la rkey (record key) de l'AT-URI du post.
        # L'URI est du format at://did/collection/rkey
        post_rkey = post.uri.split('/')[-1]

        # Traite uniquement les posts qui ne sont pas des réponses (potentiels posts racines de threads)
        # et qui n'ont pas encore été traités.
        if not post.record.reply and post.uri not in processed_thread_uris:
            print(f"Found potential thread root: {post.uri}")
            try:
                # Récupère le thread complet pour le post racine.
                # 'depth' contrôle le nombre de niveaux de réponses à récupérer.
                thread_response = client.app.bsky.feed.get_post_thread({'uri': post.uri, 'depth': 5})
                thread_view = thread_response.thread

                # Vérifie que le thread_view contient bien le post racine que nous avons demandé.
                if thread_view and thread_view.post and thread_view.post.uri == post.uri:
                    # Marque tous les posts du thread comme traités pour éviter les duplications futures.
                    def mark_posts_in_thread_as_processed(t_view_node):
                        if t_view_node.post:
                            processed_thread_uris.add(t_view_node.post.uri)
                        if t_view_node.replies:
                            for r_t_view_node in t_view_node.replies:
                                mark_posts_in_thread_as_processed(r_t_view_node)
                    mark_posts_in_thread_as_processed(thread_view)

                    # Génère la structure de données de tous les posts du thread pour le Front Matter.
                    thread_posts_data = process_thread_recursive(thread_view)

                    # Détermine le titre principal du post Jekyll (le titre de la page du thread).
                    # Il prendra le titre généré du post racine.
                    main_post_title = "Bluesky Thread"
                    main_post_description = "" # Initialise la description principale de l'article
                    main_post_image = None # Initialise la balise image principale (taille réelle)
                    main_post_thumb = None # Initialise la balise miniature principale
                    main_source_url = None # Nouvelle: URL de l'article source
                    main_source_domain = None # Nouvelle: Domaine de l'article source

                    if thread_posts_data and thread_posts_data[0]['is_root']:
                        main_post_title = thread_posts_data[0]['title']
                        # Assigne le texte complet du post racine comme description principale de l'article
                        main_post_description = thread_posts_data[0]['text'] # Ce texte aura déjà l'URL supprimée

                        # --- LOGIQUE POUR EXTRAIRE L'IMAGE ET LA MINIATURE DU POST RACINE ---
                        root_bsky_post = thread_view.post # Accès direct à l'objet post Bluesky
                        if root_bsky_post.embed:
                            # Cas 1: L'embed est directement une image (peut avoir thumb)
                            if isinstance(root_bsky_post.embed, models.AppBskyEmbedImages.View):
                                if root_bsky_post.embed.images:
                                    main_post_image = root_bsky_post.embed.images[0].fullsize
                                    main_post_thumb = root_bsky_post.embed.images[0].thumb
                            # Cas 2: L'embed est un enregistrement avec média, et le média est une image
                            elif isinstance(root_bsky_post.embed, models.AppBskyEmbedRecordWithMedia.View) and \
                                 isinstance(root_bsky_post.embed.media, models.AppBskyEmbedImages.View):
                                if root_bsky_post.embed.media.images:
                                    main_post_image = root_bsky_post.embed.media.images[0].fullsize
                                    main_post_thumb = root_bsky_post.embed.media.images[0].thumb
                            # Cas 3: L'embed est un enregistrement (ex: post cité) qui contient lui-même des embeds
                            # On parcourt les embeds pour trouver la première image ou le premier lien externe
                            elif isinstance(root_bsky_post.embed, models.AppBskyEmbedRecord.View) and \
                                 isinstance(root_bsky_post.embed.record, models.AppBskyEmbedRecord.ViewRecord) and \
                                 hasattr(root_bsky_post.embed.record, 'embeds') and root_bsky_post.embed.record.embeds:
                                for embed_item in root_bsky_post.embed.record.embeds:
                                    if isinstance(embed_item, models.AppBskyEmbedImages.View):
                                        if embed_item.images:
                                            main_post_image = embed_item.images[0].fullsize
                                            main_post_thumb = embed_item.images[0].thumb # Corrected: access .images[0].thumb
                                            break # Prend la première image trouvée et sort
                                    # Si c'est un lien externe dans le post cité, on peut aussi prendre sa miniature
                                    elif isinstance(embed_item, models.AppBskyEmbedExternal.View):
                                        if embed_item.external.thumb:
                                            main_post_thumb = embed_item.external.thumb
                                            # LOGIQUE EXISTANTE: Extraction de l'URL source et du domaine
                                            main_source_url = embed_item.external.uri
                                            parsed_url = urllib.parse.urlparse(main_source_url)
                                            main_source_domain = parsed_url.netloc
                                            break # Prend le premier lien externe trouvé et sort (ou une image)

                        # LOGIQUE EXISTANTE: Extraction de l'URL source et du domaine directement si l'embed principal est externe
                        elif isinstance(root_bsky_post.embed, models.AppBskyEmbedExternal.View):
                            main_source_url = root_bsky_post.embed.external.uri
                            parsed_url = urllib.parse.urlparse(main_source_url)
                            main_source_domain = parsed_url.netloc
                            # Si le lien externe a aussi une miniature, on la prend
                            if root_bsky_post.embed.external.thumb:
                                main_post_thumb = root_bsky_post.embed.external.thumb

                    else:
                        # Fallback au cas où les données du post racine ne seraient pas structurées comme attendu.
                        published_date_fallback = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                        main_post_title = generate_post_title(post.record.text, published_date_fallback, post.embed)
                        main_post_description = post.record.text # Fallback pour la description aussi

                    published_date = datetime.datetime.fromisoformat(post.record.created_at.replace('Z', '+00:00'))
                    
                    # Construit le nom de fichier Jekyll:YYYY-MM-DD-RKEY.md pour une unicité forte.
                    filename = f"{published_date.strftime('%Y-%m-%d')}-{post_rkey}.md"
                    filepath = os.path.join(JEKYLL_POSTS_DIR, filename)

                    # Vérifie si le fichier existe déjà pour éviter de le recréer inutilement.
                    if os.path.exists(filepath):
                        print(f"Skipping existing thread file: {filename}")
                        continue

                    print(f"Creating thread file: {filename}")

                    # Prépare le dictionnaire pour le Front Matter YAML.
                    front_matter_data = {
                        'layout': 'bluesky_thread', # Nom du layout Jekyll à utiliser pour ce post
                        'title': main_post_title, # Titre global de la page du thread
                        'description': main_post_description, # Description complète de l'article
                        'date': published_date.isoformat(), # Date de publication du post racine
                        'categories': 'bluesky',
                        'tags': ['bluesky', 'thread', 'microblogging'],
                        'bluesky_thread_url': post.uri, # Lien vers le post racine sur Bluesky
                        'thread_posts': thread_posts_data # La liste structurée de tous les posts du thread
                    }
                    
                    # Ajoute la balise 'image' si une image principale a été trouvée
                    if main_post_image:
                        front_matter_data['image'] = main_post_image
                    
                    # Ajoute la balise 'thumb' si une miniature principale a été trouvée
                    if main_post_thumb:
                        front_matter_data['thumb'] = main_post_thumb
                    
                    # AJOUT NOUVEAU: Ajoute l'URL de la source et son domaine
                    if main_source_url:
                        front_matter_data['source_url'] = main_source_url
                    if main_source_domain:
                        front_matter_data['source_domain'] = main_source_domain


                    # Convertit le dictionnaire en une chaîne YAML formatée.
                    front_matter_str = yaml.dump(front_matter_data, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2,
                                                 width=float('inf')) # Empêche le wrapping de lignes pour la description

                    # YAML.dump peut ajouter un saut de ligne en trop à la fin, on le retire si nécessaire
                    if front_matter_str.endswith('\n\n'):
                        front_matter_str = front_matter_str.strip() + '\n'


                    # Construit le contenu complet du fichier Markdown.
                    # Le corps du fichier .md lui-même est minimal, car le layout utilise le Front Matter.
                    markdown_content = f"""---
{front_matter_str}---

Ce post contient un thread Bluesky synchronisé depuis mon compte @{BLUESKY_USERNAME}.
"""
                    # Écrit le contenu dans le fichier .md.
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(markdown_content)
                else:
                    print(f"Post {post.uri} is a reply or thread structure not as expected, skipping as root.")
            except Exception as e:
                print(f"Error processing thread for {post.uri}: {e}")
                # Imprime la trace complète de l'erreur pour le débogage.
                import traceback
                traceback.print_exc()

    print("Done creating Jekyll posts from Bluesky threads.")

# Point d'entrée du script.
if __name__ == "__main__":
    # Crée le dossier _posts s'il n'existe pas.
    if not os.path.exists(JEKYLL_POSTS_DIR):
        os.makedirs(JEKYLL_POSTS_DIR)
        print(f"Created directory: {JEKYLL_POSTS_DIR}")

    fetch_and_create_threaded_posts()