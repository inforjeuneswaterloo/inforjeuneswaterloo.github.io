require 'net/http'
require 'json'
require 'uri'
require 'cgi'

module Jekyll
  class MastodonPinnedTag < Liquid::Tag
    @cache_data = nil

    class << self
      attr_accessor :cache_data
    end

    def initialize(tag_name, text, tokens)
      super
    end

    def render(context)
      instance = "mastodon.social"
      author_account_id = "110700922857450296"

      # Cache simple (plus besoin de différencier les pages)
      if MastodonPinnedTag.cache_data
        return MastodonPinnedTag.cache_data
      end

      url = "https://#{instance}/api/v1/accounts/#{author_account_id}/statuses?pinned=true"

      begin
        uri = URI.parse(url)
        response = Net::HTTP.get_response(uri)
        return "" unless response.code == "200"

        pinned_posts = JSON.parse(response.body)
        return "" if pinned_posts.empty?

        # On garde strictement les 2 derniers posts épinglés
        pinned_posts = pinned_posts.first(2)

        # Grille Bootstrap (row)
        html = '<div class="row g-4 mastodon-bootstrap-grid">'
        
        pinned_posts.each do |post|
          html << render_bootstrap_card(post)
        end

        html << '</div>'

        MastodonPinnedTag.cache_data = html
        return html

      rescue => e
        return "" 
      end
    end

    private

    def render_bootstrap_card(post)
      content_html = post['content']
      mastodon_url = post['url']

      source_url = nil
      source_title = "Actualité"

      if post['card']
        source_url = post['card']['url']
        source_title = post['card']['title'] || source_title
      end
      
      if source_url.nil? || source_url.empty?
        links = content_html.scan(/href="([^"]+)"/)
        links.each do |l|
          found_url = l.first
          unless found_url.include?("mastodon.social") || found_url.include?("/tags/")
            source_url = found_url
            break
          end
        end
      end
      
      source_url ||= mastodon_url

      img_url = nil
      if post['card'] && post['card']['image']
        img_url = post['card']['image']
      elsif post['media_attachments'] && post['media_attachments'].any?
        img_url = post['media_attachments'][0]['preview_url'] || post['media_attachments'][0]['url']
      end

      # Conteneur d'image sans rognage
      img_html = ""
      if img_url && !img_url.empty?
        img_html = <<~HTML
          <div class="pinned-img-container" style="background-color: #fff; text-align: center;">
            <img src="#{img_url}" class="card-img-top" alt="Illustration" style="width: 100%; height: auto; object-fit: contain;">
          </div>
        HTML
      end

      # Nettoyage du texte
      clean_text = content_html.gsub(/<br\s*\/?>/, "\n")
      clean_text = clean_text.gsub(/<\/p>/, "\n\n")
      clean_text = clean_text.gsub(/<[^>]*>/, "")
      clean_text = CGI.unescapeHTML(clean_text)

      clean_text = clean_text.gsub(source_url, "") if source_url
      clean_text = clean_text.gsub(/https?:\/\/[^\s]+/, "")
      clean_text = clean_text.gsub(/#\w+/, '')
      clean_text = clean_text.strip

      formatted_paragraphs = clean_text.split("\n\n").reject(&:empty?).map { |p| "<p class='card-text'>#{p.strip}</p>" }.join

      # Structure Bootstrap 2 colonnes (col-md-6) avec bouton aligné à droite
      <<~HTML
        <div class="col-12 col-md-6 d-flex align-items-stretch">
          <div class="card w-100 m-0 custom-mastodon-card" style="border: 2px solid #f1c40f; border-radius: 12px; display: flex; flex-direction: column;">
            #{img_html}
            <div class="card-body d-flex flex-column" style="flex-grow: 1; padding: 1.25rem;">
              <h3 class="card-title h5 mb-3" style="color: #222; line-height: 1.4; font-weight: 700;">#{source_title}</h3>
              <div class="card-text-container" style="flex-grow: 1; color: #4a4a4a; font-size: 0.95rem; line-height: 1.5;">
                #{formatted_paragraphs}
              </div>
              <div class="w-100 text-end text-right mt-3">
                <a href="#{source_url}" target="_blank" rel="noopener noreferrer" class="cat-button">
                  En savoir plus →
                </a>
              </div>
            </div>
          </div>
        </div>
      HTML
    end
  end
end

Liquid::Template.register_tag('mastodon_pinned', Jekyll::MastodonPinnedTag)