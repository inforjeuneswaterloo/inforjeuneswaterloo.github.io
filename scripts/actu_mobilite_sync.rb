require 'rss'
require 'open-uri'
require 'json'
require 'fileutils'

URL = 'https://mobilitedesjeunes.be/?format=feed&type=rss'
# Chemin explicite par rapport aux dossiers du projet
OUTPUT_DIR = File.expand_path('../_data', __dir__)
OUTPUT_FILE = File.join(OUTPUT_DIR, 'mobilitejeunes.json')

begin
  puts "Fetching RSS feed from #{URL}..."
  
  URI.open(URL, 'User-Agent' => 'Ruby/Jekyll-Sync-Script', read_timeout: 10) do |rss_data|
    feed = RSS::Parser.parse(rss_data, false)
    
    items = feed.items.take(5).map do |item|
      {
        'title'       => item.title,
        'link'        => item.link,
        'pubDate'     => item.pubDate ? item.pubDate.strftime('%d/%m/%Y') : '',
        'description' => item.description
      }
    end

    # 1. Force la création du dossier _data s'il n'existe pas
    FileUtils.mkdir_p(OUTPUT_DIR)
    
    # 2. Écrit le fichier JSON
    File.write(OUTPUT_FILE, JSON.pretty_generate(items))
    puts "✓ Successfully created #{OUTPUT_FILE} with #{items.size} items."
  end
rescue StandardError => e
  puts "❌ Error during RSS sync: #{e.message}"
  puts e.backtrace
  exit 1 # Force le script à renvoyer une erreur pour ne pas masquer le problème
end