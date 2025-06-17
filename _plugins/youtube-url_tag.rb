# _plugins/youtube_url_tag.rb
module Jekyll
    class YouTubeUrlTag < Liquid::Tag
      def initialize(tag_name, markup, tokens)
        super
        @youtube_url = markup.strip
      end
  
      def render(context)
        if @youtube_url.empty?
          "Error: No YouTube URL provided."
        elsif @youtube_url.include?("youtu.be/")
          youtube_id = @youtube_url.split('/').last
          "<div class=\"ratio ratio-16x9\" style=\"width:100%\">" \
            "<iframe style=\"width: 100%; height: 100%;\" src=\"https://www.youtube.com/embed/#{youtube_id}\" allowfullscreen frameborder=\"0\"></iframe>" \
          "</div>"
        elsif @youtube_url.include?("www.youtube.com/watch?v=")
          uri = URI.parse(@youtube_url)
          params = URI.decode_www_form(uri.query).to_h
          if params['v']
            video_id = params['v']
           "<div class=\"ratio ratio-16x9\" style=\"width: 100%;\">" \
          "<iframe style=\"width: 100%; height: 100%;\" src=\"https://www.youtube.com/embed/#{@youtube_id}\" allowfullscreen frameborder=\"0\"></iframe>" \
        "</div>"
          else
            "Error: Invalid YouTube URL."
          end
        else
          "Error: Invalid YouTube URL."
        end
      end
    end
  end
  
  Liquid::Template.register_tag('youtube_url', Jekyll::YouTubeUrlTag)