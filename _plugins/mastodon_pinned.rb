require 'net/http'
require 'json'
require 'uri'

module Jekyll
  class MastodonPinnedTag < Liquid::Tag
    def render(context)
      # Configuration
      account_id = "110700922857450296"
      base_url = "https://mastodon.social"
      
      begin
        # 1. RÉCUPÉRER LES POSTS ÉPINGLÉS (Mastodon en renvoie une liste)
        url = "#{base_url}/api/v1/accounts/#{account_id}/statuses?pinned=true"
        uri = URI.parse(url)
        response = Net::HTTP.get_response(uri)
        
        return "" unless response.code == "200"
        
        pinned_posts = JSON.parse(response.body)
        return "" if pinned_posts.empty? # Si aucun post n'est épinglé

        # On prend le premier post épinglé
        post = pinned_posts.first
        content = post['content']
        date = Date.parse(post['created_at']).strftime('%d/%m/%Y')
        
        # 2. NETTOYAGE DU CONTENU (Hashtags et liens internes)
        content = content.gsub(/<a [^>]*class="[^"]*hashtag[^"]*"[^>]*>#<span>[^<]*<\/span><\/a>/i, '')
        content = content.gsub(/<a [^>]*>.*?<\/a>/i, '')

        # 3. GESTION DES MÉDIAS ET LIEN
        destination_url = post['url']
        img_url = ""
        title = ""
        source_name = URI.parse(post['url']).host.sub(/^www\./, '')

        if post['card']
          destination_url = post['card']['url']
          title = post['card']['title']
          img_url = post['card']['image']
          source_name = URI.parse(destination_url).host.sub(/^www\./, '') rescue source_name
        elsif post['media_attachments'] && post['media_attachments'].any?
          img_url = post['media_attachments'][0]['preview_url']
        end

        image_html = img_url && !img_url.empty? ? "<div class='pinned-image'><img src='#{img_url}' alt=''></div>" : ""

        # 4. GÉNÉRATION DU HTML
        <<~HTML
          <div class="pinned-post-container">
            <div class="pinned-label"><i data-lucide="pin"></i>&nbsp;Epinglé</div>
            <div class="pinned-content">
              #{image_html}
              <div class="pinned-text">
                #{title.empty? ? '' : "<h3 class='mastodon-title' style='font-size:1rem; margin-bottom:5px;'>#{title}</h3>"}
                <div class="mastodon-text" style="font-size:0.9rem; line-height:1.4;">#{content}</div>
                <a href="#{destination_url}" target="_blank" class="pinned-link">En savoir plus sur #{source_name} →</a>
              </div>
            </div>
          </div>
        HTML
      rescue => e
        "" # Discret en cas d'erreur
      end
    end
  end
end

Liquid::Template.register_tag('mastodon_pinned', Jekyll::MastodonPinnedTag)