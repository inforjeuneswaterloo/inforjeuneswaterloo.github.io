# _plugins/button_tag.rb
module Jekyll
  class ButtonTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      # Découpage des arguments et évaluation des variables Liquid dans le contexte courant
      parts = @markup.split(',').map do |p|
        evaluated = Liquid::Template.parse(p).render(context)
        evaluated.strip.gsub(/\A["']|["']\Z/, '')
      end

      text       = parts[0].to_s.empty? ? 'Bouton' : parts[0]
      target_url = parts[1].to_s.empty? ? '#' : parts[1]
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

      # Balise Icône Lucide (ex: icon="calendar" ou icon="calendar-fold")
      icon_html = icon && !icon.empty? ? "<i data-lucide=\"#{icon}\" class=\"me-1\"></i>" : ""

      # HTML généré
      <<~HTML
        <a href="#{url}" class="#{btn_class} px-2 py-1 rounded text-decoration-none d-inline-flex align-items-center" target="#{target_attr}" #{rel_attr}>
          #{icon_html}<span>#{text}</span>
        </a>
      HTML
    end
  end
end

Liquid::Template.register_tag('button', Jekyll::ButtonTag)