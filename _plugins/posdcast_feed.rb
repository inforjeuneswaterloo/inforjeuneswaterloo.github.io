require 'net/http'
require 'uri'
require 'rexml/document'
require 'cgi'
require 'time'

module Jekyll
  class PodcastFeedTag < Liquid::Tag
    def render(_context)
      rss_url = "https://anchor.fm/s/f48553a0/podcast/rss"

      begin
        uri = URI.parse(rss_url)
        http = Net::HTTP.new(uri.host, uri.port)
        http.use_ssl = (uri.scheme == 'https')
        http.open_timeout = 5
        http.read_timeout = 5

        response = http.request(Net::HTTP::Get.new(uri))

        return "<p class='text-muted'>Podcast temporairement indisponible.</p>" unless response.is_a?(Net::HTTPSuccess)

        xml = REXML::Document.new(response.body)

        html = +'<ul class="list-group list-group-flush">'
        items = REXML::XPath.match(xml, "//item").first(6)

        items.each do |item|
          title = item.elements['title']&.text.to_s
          pub_date_str = item.elements['pubDate']&.text.to_s
          description = item.elements['description']&.text.to_s

          # URL du fichier audio MP3
          enclosure_node = REXML::XPath.first(item, ".//*[local-name()='enclosure']")
          audio_url = enclosure_node&.attributes&.fetch('url', nil)

          # Date et texte nettoyé
          date = Time.parse(pub_date_str).strftime('%d/%m/%Y') rescue ""
          clean_text = CGI.unescapeHTML(description).gsub(/<\/?[^>]+(>|$)/, "").strip
          truncated_text = clean_text.length > 120 ? "#{clean_text[0..120]}..." : clean_text

          # Lecteur HTML5
          audio_markup = if audio_url && !audio_url.empty?
            "<audio controls preload='none' src='#{CGI.escapeHTML(audio_url)}' class='w-100 mt-2' style='height: 36px;'></audio>"
          else
            ""
          end

          html << <<~HTML
            <li class="list-group-item py-3 px-0 border-bottom">
              <div class="w-100">
                <div class="d-flex justify-content-between align-items-baseline mb-1">
                  <h3 class="h6 mb-0 fw-bold text-dark text-truncate">#{CGI.escapeHTML(title)}</h3>
                  <small class="text-muted ms-2 flex-shrink-0">#{date}</small>
                </div>
                <p class="text-secondary small mb-1 lh-sm">#{CGI.escapeHTML(truncated_text)}</p>
                #{audio_markup}
              </div>
            </li>
          HTML
        end

        html << '</ul>'
        html
      rescue StandardError => e
        Jekyll.logger.warn "PodcastFeedTag Error:", e.message
        ""
      end
    end
  end
end

Liquid::Template.register_tag('podcast_feed', Jekyll::PodcastFeedTag)