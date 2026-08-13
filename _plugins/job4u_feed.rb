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
          html = '<div class="row g-2">'
          
          
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
              <div class=" col-sm-12 col-md-6 d-flex align-items-stretch mb-1">
                <div class="card h-100 border-0 mb-1">
                  <div class="card-body lh-sm d-flex flex-column" style="flex-grow: 1; padding: 1.25rem;">
                    <div class="d-flex justify-content-end mb-2">
                      <div class="mb-2 text-muted">
                        #{date}
                      </div>
                    </div>
                    <div class="card-text lh-sm">
                        #{text}
                    </div>
                    <div class="w-100 text-end text-right mt-auto pt-3">
                        <a href="#{destination_url}" target="_blank" rel="noopener noreferrer" class=" text-decoration-none">
                        En savoir plus&nbsp;<i data-lucide="move-right"></i>  
                        </a>
                    </div>
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