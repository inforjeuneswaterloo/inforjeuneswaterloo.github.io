module Jekyll
  class ButtonTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      # On évalue les variables ou chaînes fournies dans le contexte Liquid
      raw_args = Liquid::Template.parse("{% array #{@markup} %}").render(context) rescue ""
      
      # Extraction propre des arguments séparés par des virgules
      parts = @markup.split(',').map { |p| p.strip.gsub(/\A["']|["']\Z/, '') }

      text   = CGI.escapeHTML(parts[0] || 'Bouton')
      target = parts[1] || '#'
      color  = (parts[2] || 'e67c22').gsub(/[^a-fA-F0-9]/, '') # Sécurité : conserve uniquement le hex
      icon   = parts[3] ? CGI.escapeHTML(parts[3]) : nil

      # Détection et construction de l'URL
      url = target.include?('@') && !target.start_with?('mailto:') ? "mailto:#{target}" : target
      url = CGI.escapeHTML(url)

      # Construction du HTML
      icon_html = icon ? "<i data-lucide=\"#{icon}\"></i> " : ""
      
      <<~HTML.strip
        <a href="#{url}" class="cat-button" style="--c: ##{color}; text-decoration: none !important;">
          #{icon_html}<span class="cat-name">#{text}</span>
        </a>
      HTML
    end
  end
end

Liquid::Template.register_tag('button', Jekyll::ButtonTag)