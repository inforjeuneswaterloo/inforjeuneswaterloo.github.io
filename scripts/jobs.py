def create_jekyll_md_file_and_get_data(status_data):
    """
    Crée un fichier Markdown Jekyll à partir des données du statut Mastodon.
    Les liens d'article et les premiers liens du toot sont conservés dans le front matter,
    mais supprimés du corps du texte du post.
    Retourne True si le fichier a été créé avec succès, False sinon.
    """
    raw_content = status_data.get('content', '')
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    clean_content_raw_text = h.handle(raw_content).strip()

    # --- PARTIE 1: EXTRACTION DES LIENS ET INFOS POUR LE FRONT MATTER ---
    # Ces liens sont extraits AVANT le nettoyage complet du texte pour s'assurer qu'on les capture.

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
    # Recherche du premier lien DIRECTEMENT dans le raw_content ou clean_content_raw_text
    # afin de le conserver pour le front matter, même s'il sera retiré du corps.
    if clean_content_raw_text:
        matches = re.findall(URL_REGEX, clean_content_raw_text)
        if matches:
            first_toot_link = matches[0]

    # --- PARTIE 2: PRÉPARATION DU CONTENU TEXTUEL POUR LE CORPS DU POST ---
    # Ici, nous supprimons toutes les URLs du texte qui sera écrit dans le corps du Markdown.
    content_for_markdown_body = re.sub(URL_REGEX, '', clean_content_raw_text).strip()

    # --- PARTIE 3: DÉTERMINATION DU TITRE ET DE LA DESCRIPTION ---
    # Le titre et la description peuvent aussi être basés sur le texte sans les URLs.
    title = None
    if card and card.get('title'):
        title = card['title']
    else:
        # Essayer de prendre la première ligne non vide du contenu SANS URLS comme titre
        title_lines = [line.strip() for line in content_for_markdown_body.split('\n') if line.strip()]
        if title_lines:
            title = title_lines[0]
        else:
            title = f"Post Mastodon du {datetime.now().strftime('%Y-%m-%d')}"

    description = None
    if card and card.get('description'):
        description = card['description'].strip()
    if not description:
        # Utiliser le texte SANS URLS pour la description
        description = content_for_markdown_body # description_from_toot_text = re.sub(URL_REGEX, '', clean_content_raw_text).strip()

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

    if url_article_reference: # Lien de la carte Mastodon
        fm['url_article_reference'] = url_article_reference
    if domaine_article_reference:
        fm['domaine_article_reference'] = domaine_article_reference

    if first_toot_link: # Premier lien trouvé dans le corps du toot (avant nettoyage)
        fm['first_toot_link'] = first_toot_link
        try:
            parsed_first_toot_link = urlparse(first_toot_link)
            fm['first_toot_link_domain'] = parsed_first_toot_link.netloc
        except Exception as e:
            print(f"Avertissement : Impossible de parser le domaine pour le premier lien du toot ({first_toot_link}): {e}")

    # --- PARTIE 5: ASSEMBLAGE FINAL ET ÉCRITURE DU FICHIER ---
    # Le corps du Markdown utilise le contenu nettoyé.
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