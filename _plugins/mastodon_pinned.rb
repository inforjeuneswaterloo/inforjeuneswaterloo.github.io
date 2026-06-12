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

        html = '<div class="mastodon-pinned-container">'
        
        pinned_posts.each do |post|
          html << render_pinned_post(post)
        end

        html << '</div>'

        MastodonPinnedTag.cache_data = html
        return html

      rescue => e
        return "" 
      end
    end

    private

    def render_pinned_post(post)
      content_html = post['content']
      mastodon_url = post['url']

      # 1. EXTRACTION DU LIEN ET DU TITRE DE LA SOURCE
      source_url = nil
      source_title = "Actualité" # Titre par défaut

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

      # 2. EXTRACTION DE L'IMAGE
      img_url = nil
      if post['card'] && post['card']['image']
        img_url = post['card']['image']
      elsif post['media_attachments'] && post['media_attachments'].any?
        img_url = post['media_attachments'][0]['preview_url'] || post['media_attachments'][0]['url']
      end

      img_html = ""
      if img_url && !img_url.empty?
        img_html = <<~HTML
          <div class="pinned-img">
            <img src="#{img_url}" alt="Illustration">
          </div>
        HTML
      end

      # 3. NETTOYAGE DU TEXTE
      clean_text = content_html.gsub(/<br\s*\/?>/, "\n")
      clean_text = clean_text.gsub(/<\/p>/, "\n\n")
      clean_text = clean_text.gsub(/<[^>]*>/, "")
      clean_text = CGI.unescapeHTML(clean_text)

      clean_text = clean_text.gsub(source_url, "") if source_url
      clean_text = clean_text.gsub(/https?:\/\/[^\s]+/, "")
      clean_text = clean_text.gsub(/#\w+/, '')
      clean_text = clean_text.strip

      formatted_paragraphs = clean_text.split("\n\n").reject(&:empty?).map { |p| "<p>#{p.strip}</p>" }.join

      # Structure HTML modifiée avec le Titre inclus
      <<~HTML
        <div class="pinned-card">
          <div class="pinned-main-content">
            <h3 class="pinned-title">#{source_title}</h3>
            <div class="pinned-content-wrapper">
              #{img_html}
              <div class="pinned-text-area">
                <div class="pinned-text">
                  #{formatted_paragraphs}
                </div>
                <a href="#{source_url}" target="_blank" rel="noopener noreferrer" class="pinned-more-link">
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