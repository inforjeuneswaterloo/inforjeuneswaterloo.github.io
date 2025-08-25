# _plugins/image_tag.rb

module Jekyll
  class ImageTag < Liquid::Tag
    def initialize(tag_name, text, tokens)
      super
      @text = text
    end

    def render(context)
      parts = @text.split(',')
      url = parts[0].strip
      alt = parts[1].strip if parts.size > 1
      alt ||= "Une image"
      
      "<img src='#{url}' alt='#{alt}' class='img-fluid'>"
    end
  end
end

Liquid::Template.register_tag('image', Jekyll::ImageTag)