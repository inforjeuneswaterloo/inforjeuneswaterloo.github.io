module Jekyll
  class NoticeTag < Liquid::Block
    def initialize(tag_name, markup, tokens)
      super
      type = markup.strip
      @notice_type = type.empty? ? 'info' : type
    end

    def render(context)
      site = context.registers[:site]
      converter = if site.respond_to?(:find_converter_instance)
                    site.find_converter_instance(Jekyll::Converters::Markdown)
                  else
                    site.converters.find { |c| c.is_a?(Jekyll::Converters::Markdown) }
                  end

      content = super.to_s.strip
      markdown_content = converter.convert(content).strip

      # Remplace <p> par <p class="mb-0"> pour supprimer la marge du paragraphe
      markdown_content_mb0 = markdown_content.gsub('<p>', '<p class="mb-0">')

      # Combinaison de d-flex, align-items-center et mb-0 pour un centrage parfait
      "<div class=\"alert alert-#{@notice_type} d-flex align-items-center p-3 my-3\" role=\"alert\">" \
        "#{markdown_content_mb0}" \
      "</div>"
    end
  end
end

Liquid::Template.register_tag('notice', Jekyll::NoticeTag)