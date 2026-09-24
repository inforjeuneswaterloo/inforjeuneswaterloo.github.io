module Jekyll
  class ButtonTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      # Arguments : {% button "Texte", "URL/Mail", "Nom_Icone", "Target", "Classe_CSS" %}
      parts = @markup.split(',').map { |p| p.strip.gsub(/\A["']|["']\Z/, '') }

      text       = parts[0] || 'Bouton'
      target_url = parts[1] || '#'
      icon       = parts[2]
      custom_tgt = parts[3]
      custom_cls = parts[4] # Classe CSS personnalisée (ex: whatsapp, btn-danger, etc.)

      # Détection mailto
      url = target_url.include?('@') && !target_url.start_with?('mailto:') ? "mailto:#{target_url}" : target_url

      # Gestion de la cible (Target)
      target_attr = if custom_tgt && !custom_tgt.empty?
                      custom_tgt
                    elsif url.start_with?('http://', 'https://')
                      '_blank'
                    else
                      '_self'
                    end

      rel_attr = target_attr == '_blank' ? 'rel="noopener noreferrer"' : ''

      # Classe CSS par défaut : 'cobalt' si aucun argument n'est fourni
      btn_class = custom_cls && !custom_cls.empty? ? custom_cls : 'cobalt'

      # Balise Icône
      icon_html = icon && !icon.empty? ? "<i class=\"#{icon} me-1\"></i>" : ""

      # HTML généré
      <<~HTML
        <a href="#{url}" class="#{btn_class} px-2 py-1 rounded text-decoration-none d-inline-flex align-items-center" target="#{target_attr}" #{rel_attr}>
          #{icon_html}<span>#{text}</span>
        </a>
      HTML
    end
  end

  Liquid::Template.register_tag('button', Jekyll::ButtonTag)
end