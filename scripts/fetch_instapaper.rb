require 'open-uri'
require 'rss'
require 'yaml'
require 'fileutils'

FileUtils.mkdir_p('_data')

# Correspondance entre le fichier YAML généré dans _data/ et la variable Netlify
feeds = {
  "instapaper_home"  => "https://www.instapaper.com/rss/folder/5423670/16799378/ehwFPbnTRGx0z8DQjp3jmZoZ9E",
}

feeds.each do |filename, url|
  if url.nil? || url.strip.empty?
    puts "⚠️  Variable pour #{filename} non définie. Ignoré."
    next
  end

  begin
    target_url = url.include?('?') ? "#{url}&count=100" : "#{url}?count=100"
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    content = URI.open(target_url, "User-Agent" => user_agent).read

    rss = RSS::Parser.parse(content, false)
    
    if rss
      data = rss.items.map do |item|
        link = item.respond_to?(:link) ? (item.link.is_a?(String) ? item.link : item.link.href) : '#'
        title = item.respond_to?(:title) ? item.title : 'Sans titre'
        { "title" => title, "link" => link }
      end

      File.write("_data/#{filename}.yml", data.to_yaml)
      puts "✅ _data/#{filename}.yml généré (#{data.size} articles)"
    end

  rescue => e
    puts "❌ Erreur sur #{filename}: #{e.message}"
  end
end