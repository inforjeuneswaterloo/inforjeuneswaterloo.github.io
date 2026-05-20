require 'net/http'
require 'json'
require 'uri'

module Jekyll
  class Job4uFeedTag < Liquid::Tag
    def render(context)
      # Configuration avec le DID exact récupéré
      actor_did = "did:plc:ob2khl3reouin6l4dntfslex"
      url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=#{actor_did}&limit=6"
      
      begin
        uri = URI.parse(url)
        response = Net::HTTP.get_response(uri)
        
        if response.code == "200"
          data = JSON.parse(response.body)
          html = '<div class="mastodon-feed">'
          
          data['feed'].each do |item|
            post = item['post']
            record = post['record']
            
            next if record['reply']

            date = Time.parse(record['createdAt']).strftime('%d/%m/%Y')
            text = record['text']
            
            # Nettoyage des hashtags
            text = text.gsub(/#\w+/, '').strip

            # Définition du lien vers le post
            post_id = post['uri'].split('/').last
            destination_url = "https://bsky.app/profile/#{actor_did}/post/#{post_id}"
            img_url = ""
            title = ""
            source_name = "Job4u"

            if post['embed'] && post['embed']['$type'] == "app.bsky.embed.external#view"
              external = post['embed']['external']
              title = external['title']
              img_url = external['thumb']
              destination_url = external['uri']
              source_name = URI.parse(destination_url).host.sub(/^www\./, '') rescue "Job4u"
            elsif post['embed'] && post['embed']['images']
              img_url = post['embed']['images'][0]['thumb']
            end

            image_header = img_url && !img_url.empty? ? "<div class='mastodon-card-image'><img src='#{img_url}' alt=''></div>" : ""

            html << <<~HTML
              <div class="mastodon-post-card">
                #{image_header}
                <div class="mastodon-card-content">
                  <div class="mastodon-card-header">
                    <div class="header-left">
                      <span class="mastodon-source">#{source_name}</span>
                      <span class="mastodon-date">#{date}</span>
                    </div>
                    <a href="#{destination_url}" target="_blank" class="mastodon-footer-link">Voir l'offre →</a>
                  </div>
                  <div class="mastodon-body">
                    #{title.empty? ? '' : "<h3 class='mastodon-title'>#{title}</h3>"}
                    <div class="mastodon-text">#{text}</div>
                  </div>
                </div>
              </div>
            HTML
          end
          
          html << '</div>'
          return html
        else
          return "<p class='error'>Flux Job4u temporairement indisponible.</p>"
        end
      rescue => e
        return ""
      end
    end
  end
end

Liquid::Template.register_tag('job4u_feed', Jekyll::Job4uFeedTag)