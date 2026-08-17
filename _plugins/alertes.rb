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

      # Définition de la classe Bootstrap
      bs_class = case @type
                 when "info" then "alert-info"
                 when "warning" then "alert-warning"
                 when "success" then "alert-success"
                 when "danger" then "alert-danger"
                 else "alert-secondary"
                 end

      # Rendu HTML Bootstrap sans icône
      <<-HTML
<div class="alert #{bs_class} my-3" role="alert">
  <div class="alert-content">
    #{content}
  </div>
</div>
      HTML
    end
  end
end

Liquid::Template.register_tag('alert', Jekyll::AlertBlock)