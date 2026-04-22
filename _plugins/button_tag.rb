module Jekyll
  class ButtonTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      # On sépare par virgule : {% button "Texte", "URL/Mail", "Couleur_Hex", "Nom_Icone" %}
      parts = @markup.split(',').map { |p| p.strip.gsub(/\A["']|["']\Z/, '') }

      text  = parts[0] || 'Bouton'
      target = parts[1] || '#'
      # On nettoie la couleur pour s'assurer qu'il n'y a pas de double #
      color = (parts[2] || 'e67c22').delete('#') 
      icon  = parts[3] # L'icône Lucide

      # Détection mailto
      url = target.include?('@') ? "mailto:#{target}" : target

      # Construction du HTML
      html =  "<a href=\"#{url}\" class=\"cat-button\" style=\"--c: ##{color}; text-decoration: none !important;\">"
      html += "<i data-lucide=\"#{icon}\"></i> " if icon
      html += "<span class=\"cat-name\">#{text}</span>"
      html += "</a>"

      html
    end
  end

  Liquid::Template.register_tag('button', Jekyll::ButtonTag)
end