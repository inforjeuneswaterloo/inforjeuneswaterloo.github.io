require 'open-uri'
require 'rss'
require 'yaml'
require 'fileutils'

FileUtils.mkdir_p('_data')

# Dictionnaire des flux (Clé = nom du fichier dans _data, Valeur = Variable d'environnement)
feeds = {
  "instapaper_home"  => ENV["INSTAPAPER_HOME_RSS"],
  "instapaper_tech"  => ENV["INSTAPAPER_TAG_TECH"],
  "instapaper_sante" => ENV["INSTAPAPER_TAG_SANTE"]
}

feeds.each do |filename, url|
  if url.nil? || url.strip.empty?
    puts "⚠️  Variable pour #{filename} non définie ou vide. Ignoré."
    next
  end

  begin
    # Forcer la récupération de 100 éléments au lieu de 10 par défaut
    target_url = url.include?('?') ? "#{url}&count=100" : "#{url}?count=100"

    # Navigation sécurisée avec un User-Agent
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
      puts "✅ _data/#{filename}.yml généré (#{data.size} éléments)"
    else
      puts "❌ Impossible de lire le flux RSS pour #{filename}"
    end

  rescue => e
    puts "❌ Erreur sur #{filename}: #{e.message}"
  end
end