require 'rss'
require 'open-uri'
require 'json'
require 'fileutils'

URL = 'https://mobilitedesjeunes.be/?format=feed&type=rss'
OUTPUT_FILE = '_data/mobilitedesjeunes.json'

begin
  puts "Fetching RSS feed from #{URL}..."
  # Configuration d'un User-Agent et d'un Timeout de 10 sec pour éviter les blocages
  URI.open(URL, 'User-Agent' => 'Ruby/Jekyll-Sync-Script', read_timeout: 10) do |rss_data|
    feed = RSS::Parser.parse(rss_data, false)
    
    items = feed.items.take(5).map do |item| # Récupère les 5 derniers articles
      {
        'title'       => item.title,
        'link'        => item.link,
        'pubDate'     => item.pubDate.strftime('%d/%m/%Y'),
        'description' => item.description
      }
    end

    # S'assure que le dossier _data existe
    FileUtils.mkdir_p('_data')
    
    # Sauvegarde au format JSON propre pour Jekyll
    File.write(OUTPUT_FILE, JSON.pretty_generate(items))
    puts "✓ Saved #{items.size} feed items to #{OUTPUT_FILE}"
  end
rescue StandardError => e
  puts "⚠️ Warning: Failed to fetch feed: #{e.message}"
  # Si le fichier existe déjà (d'un build précédent), on le conserve sans crasher
  unless File.exist?(OUTPUT_FILE)
    File.write(OUTPUT_FILE, '[]')
  end
end