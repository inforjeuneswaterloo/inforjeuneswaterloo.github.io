require 'net/http'
require 'json'
require 'uri'
require 'time'
require 'cgi'

module Jekyll
  class ActuFeedTag < Liquid::Tag
    @cache_data = nil

    class << self
      attr_accessor :cache_data
    end

    def initialize(tag_name, text, tokens)
      super
    end

    def render(context)
      # Mise à jour avec ton nouveau DID exact
      actor_did = "did:plc:rtnecm24l37p42guu4wwwwqq"
      url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=#{actor_did}&limit=12"
      
      if ActuFeedTag.cache_data
        return ActuFeedTag.cache_data
      end

      begin
        uri = URI.parse(url)
        response = Net::HTTP.get_response(uri)
        return "" unless response.code == "200"
        
        data = JSON.parse(response.body)
        return "" if data['feed'].nil? || data['feed'].empty?

        html = '<div class="row g-4 bsky-bootstrap-grid">'
        count = 0

        data['feed'].each do |item|
          break if count >= 4 # Limite stricte aux 4 premiers posts valides

          post = item['post']
          record = post['record']
          
          # On ignore les réponses pour ne garder que les posts principaux
          next if record['reply']

          text = record['text'] || ""
          
          # Suppression des hashtags (#Tag)
          text = text.gsub(/#\w+/, '').strip
          formatted_text = CGI.escapeHTML(text).split("\n\n").reject(&:empty?).map { |p| "<p class='card-text'>#{p.strip}</p>" }.join

          post_id = post['uri'].split('/').last
          bsky_post_url = "https://bsky.app/profile/#{actor_did}/post/#{post_id}"
          
          destination_url = bsky_post_url
          img_url = nil
          title = "Actualité"

          # Extraction de l'image source et redirection vers le lien d'origine
          if post['embed']
            embed_type = post['embed']['$type']
            
            if embed_type.include?("app.bsky.embed.external")
              external = post['embed']['external']
              title = external['title'] || title
              img_url = external['thumb']
              
              # Renvoie directement vers la source de presse d'origine
              destination_url = external['uri'] || bsky_post_url
            elsif embed_type.include?("app.bsky.embed.images") && post['embed']['images'] && post['embed']['images'].any?
              img_url = post['embed']['images'][0]['thumb'] || post['embed']['images'][0]['fullsize']
            end
          end

          media_name = URI.parse(destination_url).host.sub(/^www\./, '') rescue "Source"

          # Gestion de l'image (anti-tronquage)
          img_html = ""
          if img_url && !img_url.empty?
            img_html = <<~HTML
                <img src="#{img_url}" class="card-img-top" alt="Illustration" style="width: 100%; height: auto; object-fit: contain;">
            HTML
          end

          # Rendu en grille Bootstrap 2 colonnes avec alignement du bouton .cat-button à droite
          html << <<~HTML
            <div class="col-12 col-md-6 d-flex align-items-stretch mb-3">
                <div class="card h-100 border-0 mb-2">
                    #{img_html}
                    <div class="card-body lh-sm d-flex flex-column" style="flex-grow: 1; padding: 1.25rem;">
                    <span class="mb-2 text-muted" style="font-size: 0.8rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                        #{media_name}
                    </span>
                    <h3 class="card-title h5 mb-2 lh-sm" style="color: #222; line-height: 1.4; font-weight: 700;">#{CGI.escapeHTML(title)}</h3>
                    <div class="card-text lh-sm">
                        #{formatted_text}
                    </div>
                    <div class="w-100 text-end text-right mt-auto pt-3">
                        <a href="#{destination_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-dark">
                        En savoir plus&nbsp;<i data-lucide="move-right"></i>  
 

                        </a>
                    </div>
                    </div>
                </div>
            </div>
          HTML

          count += 1
        end
        
        html << '</div>'
        
        ActuFeedTag.cache_data = html
        return html

      rescue => e
        return ""
      end
    end
  end
end

Liquid::Template.register_tag('actu', Jekyll::ActuFeedTag)