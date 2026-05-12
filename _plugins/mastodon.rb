require 'net/http'
require 'json'
require 'uri'
require 'cgi'

module Jekyll
  class MastodonFeedTag < Liquid::Tag
    def render(context)
      account_id = "110700922857450296"
      url = "https://mastodon.social/api/v1/accounts/#{account_id}/statuses?limit=6&exclude_reblogs=true"
      
      begin
        uri = URI.parse(url)
        http = Net::HTTP.new(uri.host, uri.port)
        http.use_ssl = true
        http.open_timeout = 5
        http.read_timeout = 5
        response = http.get(uri.request_uri)
        
        if response.code == "200"
          posts = JSON.parse(response.body)
          html = '<div class="mastodon-feed">'
          
          posts.each do |post|
            next unless post['in_reply_to_id'].nil?

            date = Date.parse(post['created_at']).strftime('%d/%m/%Y')
            content = post['content']
            
            # 1. NETTOYAGE RADICAL
            # Supprime les Hashtags (Balise + Texte #Tag)
            content = content.gsub(/<a [^>]*class="[^"]*hashtag[^"]*"[^>]*>#<span>[^<]*<\/span><\/a>/i, '')
            
            # Supprime TOUS les autres liens (Balise + Texte du lien)
            # Cela nettoie les mentions et les URLs citées dans le corps du texte
            content = content.gsub(/<a [^>]*>.*?<\/a>/i, '')

            # 2. RÉCUPÉRATION DES MÉDIAS ET DU LIEN SOURCE
            destination_url = post['url']
            img_url = ""
            title = ""
            source_name = "Mastodon"

            if post['card']
              destination_url = post['card']['url']
              title = post['card']['title']
              img_url = post['card']['image']
              source_name = URI.parse(destination_url).host.sub(/^www\./, '') rescue "Lien"
            elsif post['media_attachments'] && post['media_attachments'].any?
              img_url = post['media_attachments'][0]['preview_url']
            end

            image_header = img_url && !img_url.empty? ? "<div class='mastodon-card-image'><img src='#{img_url}' alt=''></div>" : ""

            html << <<~HTML
              <div class="mastodon-post-card">
                #{image_header}
                <div class="mastodon-card-content">
                  <div class="mastodon-card-header">
                    <span class="mastodon-source">#{source_name}</span>
                    <span class="mastodon-date">#{date}</span>
                  </div>
                  <div class="mastodon-body">
                    #{title.empty? ? '' : "<h3 class='mastodon-title'>#{title}</h3>"}
                    <div class="mastodon-text">#{content}</div>
                    <a href="#{destination_url}" target="_blank" class="mastodon-footer-link">
                      Lire la suite sur #{source_name} →
                    </a>
                  </div>
                </div>
              </div>
            HTML
          end
          
          html << '</div>'
          return html
        else
          return "<p class='error'>Flux indisponible.</p>"
        end
      rescue => e
        return "<p class='error'>Erreur de chargement.</p>"
      end
    end
  end
end

Liquid::Template.register_tag('mastodon_feed', Jekyll::MastodonFeedTag)