module Jekyll
  class AlertBlock < Liquid::Block
    def initialize(tag_name, type, tokens)
      super
      @type = type.strip
    end

    def render(context)
      text = super
      # Convertit le contenu Markdown en HTML
      site = context.registers[:site]
      converter = site.find_converter_instance(Jekyll::Converters::Markdown)
      content = converter.convert(text)

      # Configuration des icônes et couleurs par type
      case @type
      when "info"
        icon, color = "info", "#3498db"
      when "warning"
        icon, color = "alert-triangle", "#e67c22"
      when "success"
        icon, color = "check-circle", "#27ae60"
      when "danger"
        icon, color = "x-circle", "#e74c3c"
      else
        icon, color = "bell", "#2c3e50"
      end

      # Génère le rendu final
      <<-HTML
<div class="cat-button" style="border: 1px solid #{color}">
  <div class="alert-content">
    #{content}
  </div>
</div>
      HTML
    end
  end
end

Liquid::Template.register_tag('alert', Jekyll::AlertBlock)
