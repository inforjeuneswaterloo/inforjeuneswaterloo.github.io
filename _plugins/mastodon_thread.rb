require 'net/http'
require 'json'
require 'uri'
require 'cgi'

module Jekyll
  class MastodonThreadTag < Liquid::Tag
    # Cache global en mémoire pour éviter les requêtes HTTP redondantes durant le build
    @cache = {}

    class << self
      attr_accessor :cache
    end

    def initialize(tag_name, status_id, tokens)
      super
      @status_id = status_id.strip
    end

    def render(context)
      instance = "mastodon.social"
      author_account_id = "110700922857450296"
      
      # Si ce thread a déjà été téléchargé durant ce build, on renvoie directement le HTML stocké
      if MastodonThreadTag.cache.key?(@status_id)
        return MastodonThreadTag.cache[@status_id]
      end

      root_url = "https://#{instance}/api/v1/statuses/#{@status_id}"
      context_url = "https://#{instance}/api/v1/statuses/#{@status_id}/context"
      
      begin
        # 1. POST RACINE
        uri_root = URI.parse(root_url)
        res_root = Net::HTTP.get_response(uri_root)
        return "<p class='error'>Thread Mastodon introuvable.</p>" unless res_root.code == "200"
        root_post = JSON.parse(res_root.body)
        
        html = '<div class="bsky-thread-container">'
        html << render_post(root_post, true)
        
        # 2. LES RÉPONSES
        uri_context = URI.parse(context_url)
        res_context = Net::HTTP.get_response(uri_context)
        
        if res_context.code == "200"
          context_data = JSON.parse(res_context.body)
          descendants = context_data['descendants'] || []
          
          author_replies = descendants.select do |reply|
            reply['account']['id'].to_s == author_account_id
          end
          
          if author_replies.any?
            html << '<div class="thread-replies-wrapper">'
            
            max_replies = 5
            truncated = author_replies.size > max_replies
            
            author_replies.take(max_replies).each do |reply_post|
              html << render_post(reply_post, false)
            end
            
            html << '</div>'
            
            if truncated
              mastodon_url = root_post['url']
              html << <<~HTML
                <div class="thread-truncated-notice">
                  <a href="#{mastodon_url}" target="_blank" class="thread-more-link">
                    Lire la suite de ce fil sur Mastodon (total: #{author_replies.size + 1} posts) →
                  </a>
                </div>
              HTML
            end
          end
        end
        
        html << '</div>'
        
        # Sauvegarde du résultat dans le cache avant de le retourner
        MastodonThreadTag.cache[@status_id] = html
        return html

      rescue => e
        return "<p class='error'>Erreur de chargement du thread Mastodon.</p>"
      end
    end

    private

    def render_post(post, is_root)
      text = post['content']
      
      text = CGI.unescapeHTML(text)

      text = text.gsub(/<a[^>]*class="[^"]*hashtag[^"]*"[^>]*>#<span>\w+<\/span><\/a>/i, '')
      text = text.gsub(/#\w+/, '').strip

      text = text.gsub(/<a /i, '<a target="_blank" rel="noopener noreferrer" ')

      date = Time.parse(post['created_at']).strftime('%d/%m/%Y à %H:%M')
      card_class = is_root ? "thread-post-root" : "thread-post-reply"
      
      img_html = ""
      if post['media_attachments'] && post['media_attachments'].any?
        img_url = post['media_attachments'][0]['preview_url'] || post['media_attachments'][0]['url']
        img_html = "<div class='thread-img'><img src='#{img_url}' alt='Illustration Infor Jeunes'></div>"
      end

      <<~HTML
        <div class="#{card_class}">
          <div class="thread-meta">
            <span class="thread-author">#{post['account']['display_name'] || 'Infor Jeunes'}</span>
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

Liquid::Template.register_tag('mastodon_thread', Jekyll::MastodonThreadTag)
