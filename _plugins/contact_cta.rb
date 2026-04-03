module Jekyll
  class ContactCtaTag < Liquid::Tag
    def initialize(tag_name, input, tokens)
      super
      @input = input
    end

    def render(context)
      # Syntaxe : {% contact_btn Texte du bouton | url %}
      params = @input.split('|').map(&:strip)
      text = params[0] || "Nous contacter"
      url  = params[1] || "/contact/"
      
      # Couleur fixée sur l'orange Infor Jeunes (identique à la page contact)
      contact_color = "#e67c22"

      <<-HTML
<div class="cta-wrapper" style="margin: 2rem 0; display: flex; justify-content: center;">
  <a href="#{url}" class="cat-button" style="--c: #{contact_color}; text-decoration: none !important; display: inline-flex; align-items: center; gap: 12px; padding: 14px 25px; border-radius: 16px; border: 2px solid color-mix(in srgb, #{contact_color}, transparent 70%); transition: all 0.3s ease;">
    <i data-lucide="message-circle" style="stroke: #{contact_color}; stroke-width: 2.5px; width: 20px; height: 20px;"></i>
    <span class="cat-name" style="font-weight: 800; color: #333;">#{text}</span>
  </a>
</div>
      HTML
    end
  end
end

Liquid::Template.register_tag('contact_btn', Jekyll::ContactCtaTag)