require 'net/http'
require 'json'
require 'uri'

module Jekyll
  class BlueskyThreadTag < Liquid::Tag
    def initialize(tag_name, post_id, tokens)
      super
      @post_id = post_id.strip
    end

    def render(context)
      actor_did = "did:plc:rtnecm24l37p42guu4wwwwqq"
      post_uri = "at://#{actor_did}/app.bsky.feed.post/#{@post_id}"
      
      api_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread?uri=#{URI.encode_www_form_component(post_uri)}&depth=100"
      
      begin
        uri = URI.parse(api_url)
        response = Net::HTTP.get_response(uri)
        
        return "<p class='error'>Thread introuvable.</p>" unless response.code == "200"
        
        data = JSON.parse(response.body)
        thread = data['thread']
        
        html = '<div class="bsky-thread-container">'
        
        # 1. POST RACINE
        html << render_post(thread['post'], true)
        
        # 2. COLLECTE ET TRI DES RÉPONSES
        all_replies = []
        flatten_replies(thread, actor_did, all_replies)
        
        sorted_replies = all_replies.uniq { |r| r['uri'] }.sort_by { |r| r['record']['createdAt'] rescue "" }
        
        if sorted_replies.any?
          html << '<div class="thread-replies-wrapper">'
          
          max_replies = 5
          truncated = sorted_replies.size > max_replies
          
          sorted_replies.take(max_replies).each do |reply_post|
            html << render_post(reply_post, false)
          end
          
          html << '</div>'
          
          # 3. LE BOUTON DE SÉCURITÉ Visuelle
          if truncated
            root_post_id = thread['post']['uri'].split('/').last
            bluesky_url = "https://bsky.app/profile/#{actor_did}/post/#{root_post_id}"
            html << <<~HTML
              <div class="thread-truncated-notice">
                <a href="#{bluesky_url}" target="_blank" class="thread-more-link">
                  Lire la suite de ce fil sur Bluesky (total: #{sorted_replies.size + 1} posts) →
                </a>
              </div>
            HTML
          end
        end
        
        html << '</div>'
        return html
      rescue => e
        return "<p class='error'>Erreur de chargement du thread Bluesky.</p>"
      end
    end

    private

    def flatten_replies(node, actor_did, accumulator)
      replies = node['replies'] || (node['post'] && node['post']['replies'])
      return unless replies

      replies.each do |reply|
        post = reply['post']
        if post && post['author']['did'] == actor_did
          accumulator << post
        end
        flatten_replies(reply, actor_did, accumulator)
      end
    end

    def render_post(post, is_root)
      record = post['record']
      text_raw = record['text']
      
      # 1. RECONSTRUCTION EN DIRECT DES LIENS CLIQUABLES (FACETS)
      formatted_text = text_raw.bytes.to_a
      
      if record['facets']
        # On trie les facettes à l'envers pour ne pas décaler les index textuels lors des insertions HTML
        sorted_facets = record['facets'].sort_by { |f| -(f['index']['byteStart'] rescue 0) }
        
        sorted_facets.each do |facet|
          next unless facet['features']
          
          facet['features'].each do |feature|
            # Si la facette est un lien web
            if feature['$type'] == 'app.bsky.richtext.facet#link'
              url = feature['uri']
              b_start = facet['index']['byteStart']
              b_end = facet['index']['byteEnd']
              
              # Extraction du texte d'ancrage en octets
              anchor_bytes = formatted_text[b_start...b_end]
              anchor_text = anchor_bytes.pack('C*').force_encoding('UTF-8')
              
              # Génération de la balise HTML propre ouvrant dans un nouvel onglet
              html_link = "<a href='#{url}' target='_blank' rel='noopener noreferrer'>#{anchor_text}</a>"
              
              # Remplacement dans le tableau d'octets original
              formatted_text[b_start...b_end] = html_link.bytes.to_a
            end
          end
        end
      end
      
      # Conversion finale du tableau d'octets modifié vers du texte HTML exploitable
      text_html = formatted_text.pack('C*').force_encoding('UTF-8')

      # Nettoyage des résidus de hashtags textuels
      text_html = text_html.gsub(/#\w+/, '').strip
      
      date = Time.parse(record['createdAt']).strftime('%d/%m/%Y à %H:%M')
      card_class = is_root ? "thread-post-root" : "thread-post-reply"
      
      # 2. EXTRACTION ET AFFICHAGE DES IMAGES
      img_html = ""
      if post['embed'] && post['embed']['images']
        img_url = post['embed']['images'][0]['thumb']
        img_html = "<div class='thread-img'><img src='#{img_url}' alt='Illustration Infor Jeunes'></div>"
      end

      <<~HTML
        <div class="#{card_class}">
          <div class="thread-meta">
            <span class="thread-author">#{post['author']['displayName'] || 'Infor Jeunes'}</span>
            <span class="thread-date">#{date}</span>
          </div>
          <div class="thread-body">
            #{img_html}
            <div class="thread-text">#{text_html}</div>
          </div>
        </div>
      HTML
    end
  end
end

Liquid::Template.register_tag('bsky_thread', Jekyll::BlueskyThreadTag)