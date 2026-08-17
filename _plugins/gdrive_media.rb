require 'cgi'

module Jekyll
  class GithubVideoTag < Liquid::Tag
    def initialize(tag_name, text, tokens)
      super
      args = text.strip.split(/\s+/).map { |arg| arg.gsub(/\A["']|["']\z/, '') }
      
      if args.length > 1
        @release_tag = args[0]
        @file_name = args[1]
      else
        @release_tag = "media"
        @file_name = args[0]
      end
    end

    def render(context)
      site = context.registers[:site]
      config = site.config['github_audio'] || site.config['github_media'] || {}

      user = config['user']
      repo = config['repo']

      if user.nil? || repo.nil?
        return "<p class='text-danger small'>Veuillez configurer 'github_media' dans _config.yml.</p>"
      end

      file_url = "https://github.com/#{user}/#{repo}/releases/download/#{@release_tag}/#{@file_name}"

      <<~HTML
        <div class="ratio ratio-16x9 my-3">
          <video controls preload="metadata" class="rounded border shadow-sm w-100">
            <source src="#{CGI.escapeHTML(file_url)}" type="video/mp4">
            Votre navigateur ne supporte pas la lecture de vidéos HTML5.
          </video>
        </div>
      HTML
    end
  end
end

Liquid::Template.register_tag('github_media', Jekyll::GithubVideoTag)