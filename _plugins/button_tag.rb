module Jekyll
  class ButtonTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @markup = markup.strip
    end

    def render(context)
      parts = @markup.split(',').map(&:strip)

      text = (parts[0] && !parts[0].empty? ? parts[0].gsub(/"/,'') : 'Button')
      url = (parts[1] && !parts[1].empty? ? parts[1].gsub(/"/,'') : '#')
      style = (parts[2] && !parts[2].empty? ? parts[2].gsub(/"/,'') : 'primary')
      icon = (parts[3] && !parts[3].empty? ? parts[3].gsub(/"/,'') : nil) # Récupérer l'icône

      button_html = "<a href=\"#{url}\" class=\"btn btn-#{style}\">#{text}"
      button_html += " <i class=\"#{icon}\"></i>" if icon # Ajouter l'icône si elle est présente
      button_html += "</a>"

      button_html
    end
  end

  Liquid::Template.register_tag('button', Jekyll::ButtonTag)
end