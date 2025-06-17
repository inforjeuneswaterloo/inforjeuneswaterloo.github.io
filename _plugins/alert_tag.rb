module Jekyll
  class NoticeTag < Liquid::Block
    def initialize(tag_name, markup, tokens)
      super
      @notice_type = markup.strip # Get the 'info' from the tag
    end

    def render(context)
      site = context.registers[:site]
      converter = site.find_converter_instance(Jekyll::Converters::Markdown) # Changed method name

      content = super.to_s.strip # Get the content inside the tag
      markdown_content = converter.convert(content).strip

     # Use Bootstrap's alert classes
      "<div class=\"alert alert-#{@notice_type}\" role=\"alert\">#{markdown_content}</div>"
    end
  end

  Liquid::Template.register_tag('notice', Jekyll::NoticeTag)
end