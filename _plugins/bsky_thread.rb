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
      
      api_url = "https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread?uri=#{URI.encode_www_form_component(post_uri)}"
      
      begin
        uri = URI.parse(api_url)
        response = Net::HTTP.get_response(uri)
        
        return "<p class='error'>Thread introuvable.</p>" unless response.code == "200"
        
        data = JSON.parse(response.body)
        thread = data['thread']
        
        html = '<div class="bsky-thread-container">'
        
        # 1. LE POST PRINCIPAL (RACINE)
        html << render_post(thread['post'], true)
        
        # 2. LES RÉPONSES AVEC LIMITE
        if thread['replies'] && thread['replies'].any?
          html << '<div class="thread-replies-wrapper">'
          
          # Filtrer d'abord pour ne garder que l'auteur
          author_replies = thread['replies'].select { |r| r['post']['author']['did'] == actor_did }
          
          # Tri chronologique
          sorted_replies = author_replies.sort_by { |r| r['post']['record']['createdAt'] rescue "" }
          
          # --- LA SÉCURITÉ : On limite à 5 réponses maximum ---
          max_replies = 5
          truncated = sorted_replies.size > max_replies
          
          sorted_replies.take(max_replies).each do |reply|
            html << render_post(reply['post'], false)
          end
          
          html << '</div>'
          
          # Si on a dépassé la limite, on met un lien de redirection
          if truncated
            root_post_id = thread['post']['uri'].split('/').last
            bluesky_url = "https://bsky.app/profile/#{actor_did}/post/#{root_post_id}"
            html << <<~HTML
              <div class="thread-truncated-notice">
                <a href="#{bluesky_url}" target="_blank" class="thread-more-link">
                  Lire la suite de ce fil sur Bluesky (total: #{sorted_replies.size} posts) →
                </a>
              </div>
            HTML
          end
        end
        
        html << '</div>'
        return html
      rescue => e
        return ""
      end
    end

    private

    def render_post(post, is_root)
      record = post['record']
      text = record['text'].gsub(/#\w+/, '').strip
      date = Time.parse(record['createdAt']).strftime('%d/%m/%Y à %H:%M')
      
      card_class = is_root ? "thread-post-root" : "thread-post-reply"
      
      img_html = ""
      if post['embed'] && post['embed']['images']
        img_url = post['embed']['images'][0]['thumb']
        img_html = "<div class='thread-img'><img src='#{img_url}' alt=''></div>"
      end

      <<~HTML
        <div class="#{card_class}">
          <div class="thread-meta">
            <span class="thread-author">#{post['author']['displayName'] || 'Infor Jeunes'}</span>
            <span class="thread-date">#{date}</span>
          </div>
          <div class="thread-body">
            #{img_html}
            <div class="thread-text">#{text}</div>
          </div>
        </div>
      HTML
    end
  end
end

Liquid::Template.register_tag('bsky_thread', Jekyll::BlueskyThreadTag)