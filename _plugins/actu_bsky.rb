# _plugins/actu_feed_tag.rb
require 'net/http'
require 'json'
require 'uri'
require 'time'
require 'cgi'

module Jekyll
  class ActuFeedTag < Liquid::Tag
    @cache_data = {}

    class << self
      attr_accessor :cache_data
    end

    def initialize(tag_name, markup, tokens)
      super
      # On récupère le paramètre passé à la balise, avec 4 par défaut
      param = markup.strip
      @limit = param.empty? ? 4 : param.to_i
      @limit = 4 if @limit <= 0
    end

    def render(context)
      actor_did = "did:plc:rtnecm24l37p42guu4wwwwqq"
      # On demande un peu plus d'éléments à l'API que la limite voulue pour compenser les réponses (replies) ignorées
      fetch_limit = [@limit * 3, 100].min
      url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=#{actor_did}&limit=#{fetch_limit}"
      
      ActuFeedTag.cache_data ||= {}
      return ActuFeedTag.cache_data[@limit] if ActuFeedTag.cache_data[@limit]

      begin
        uri = URI.parse(url)
        http = Net::HTTP.new(uri.host, uri.port)
        http.use_ssl = true
        http.open_timeout = 5
        http.read_timeout = 5

        request = Net::HTTP::Get.new(uri.request_uri)
        response = http.request(request)

        return "" unless response.code == "200"
        
        data = JSON.parse(response.body)
        return "" if data['feed'].nil? || data['feed'].empty?

        html = '<div class="row g-2 bsky-bootstrap-grid">'
        count = 0

        data['feed'].each do |item|
          break if count >= @limit # Limite dynamique définie par le paramètre

          post = item['post']
          record = post['record']
          
          # Ignorer les réponses directes
          next if record['reply']

          text = record['text'] || ""
          
          # Nettoyage des hashtags
          text = text.gsub(/#\w+/, '').strip
          formatted_text = CGI.escapeHTML(text).split("\n\n").reject(&:empty?).map { |p| "<p class='card-text'>#{p.strip}</p>" }.join

          post_id = post['uri'].split('/').last
          bsky_post_url = "https://bsky.app/profile/#{actor_did}/post/#{post_id}"
          
          destination_url = bsky_post_url
          img_url = nil
          title = "Actualité"

          # Détection des pièces jointes / embeds
          if post['embed']
            embed = post['embed']
            embed_type = embed['$type'] || ""

            # Gestion des posts composés (citation + média)
            embed = embed['media'] if embed_type.include?("app.bsky.embed.recordWithMedia") && embed['media']
            embed_type = embed['$type'] || ""

            if embed_type.include?("app.bsky.embed.external") && embed['external']
              external = embed['external']
              title = external['title'] || title
              img_url = external['thumb']
              destination_url = external['uri'] || bsky_post_url
            elsif embed_type.include?("app.bsky.embed.images") && embed['images'] && embed['images'].any?
              img_url = embed['images'][0]['thumb'] || embed['images'][0]['fullsize']
            end
          end

          media_name = URI.parse(destination_url).host.sub(/^www\./, '') rescue "Source"

          # Rendu de l'illustration
          img_html = ""
          if img_url && !img_url.empty?
            img_html = <<~HTML
              <img src="#{img_url}" class="card-img-top" alt="Illustration" style="width: 100%; height: auto; object-fit: contain;">
            HTML
          end

          # Structure de carte Bootstrap
          html << <<~HTML
            <div class="col-sm-12 col-md-6 d-flex align-items-stretch mb-2">
              <div class="card h-100 border-0 bg-light shadow-sm" style="border-radius: 0.5rem; overflow: hidden;">
                #{img_html}
                <div class="card-body lh-sm d-flex flex-column" style="flex-grow: 1; padding: 1.25rem;">
                  <span class="mb-2 text-muted" style="font-size: 0.8rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                    #{CGI.escapeHTML(media_name)}
                  </span>
                  <h3 class="card-title h5 mb-2 lh-sm" style="color: #222; line-height: 1.4; font-weight: 700;">#{CGI.escapeHTML(title)}</h3>
                  <div class="card-text lh-sm">
                    #{formatted_text}
                  </div>
                  <div class="w-100 text-end mt-auto pt-3">
                    <a href="#{destination_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-dark text-white text-decoration-none" style="font-size: 0.875rem; font-weight: 500; padding: 0.375rem 0.75rem; border-radius: 0.25rem;">
                      En savoir plus&nbsp;<i data-lucide="arrow-up-right"></i>  
                    </a>
                  </div>
                </div>
              </div>
            </div>
          HTML

          count += 1
        end
        
        html << '</div>'
        
        ActuFeedTag.cache_data[@limit] = html
        return html

      rescue => e
        Jekyll.logger.warn("ActuFeedTag Error:", e.message)
        return ""
      end
    end
  end
end

Liquid::Template.register_tag('actu', Jekyll::ActuFeedTag)