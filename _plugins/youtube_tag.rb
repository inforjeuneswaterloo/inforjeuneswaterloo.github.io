module Jekyll
  class VimeoTag < Liquid::Tag
    def initialize(tag_name, markup, tokens)
      super
      @youtube_id = markup.strip
    end

    def render(context)
      if @youtube_id.empty?
        "Error: No Vimeo video ID provided."
      else
        "<div class=\"ratio ratio-16x9\" style=\"width: 100%;\">" \
          "<iframe style=\"width: 100%; height: 100%;\" src=\"https://www.youtube.com/embed/#{@youtube_id}\" allowfullscreen frameborder=\"0\"></iframe>" \
        "</div>"
      end
    end
  end
end

Liquid::Template.register_tag('youtube', Jekyll::VimeoTag)