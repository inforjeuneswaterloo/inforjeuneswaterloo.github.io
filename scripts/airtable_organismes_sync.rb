require 'net/http'
require 'json'
require 'yaml'
require 'fileutils'

# 1. Vérification des variables d'environnement
pat = ENV['AIRTABLE_PAT']
base_id = ENV['AIRTABLE_BASE_ID']
table_name = 'Organismes'

if pat.nil? || base_id.nil?
  puts "Erreur : AIRTABLE_PAT ou AIRTABLE_BASE_ID manque à l'appel."
  exit 1
end

# 2. Requête vers l'API Airtable
url = URI("https://api.airtable.com/v0/#{base_id}/#{URI.encode_www_form_component(table_name)}")
req = Net::HTTP::Get.new(url)
req['Authorization'] = "Bearer #{pat}"

response = Net::HTTP.start(url.hostname, url.port, use_ssl: true) do |http|
  http.request(req)
end

unless response.is_a?(Net::HTTPSuccess)
  puts "Erreur d'API Airtable (#{response.code}) : #{response.body}"
  exit 1
end

data = JSON.parse(response.body)
organismes = {}

# 3. Traitement des enregistrements
data['records'].each do |record|
  fields = record['fields']
  
  # Filtre de sécurité : ignore les éléments non publiés
  next unless fields['Publié'] == true

  nom = fields['Nom']
  next if nom.nil? || nom.strip.empty?

  # Génération d'une clé propre pour le hash YAML
  slug = nom.downcase
            .gsub(/[áàâäã]/, 'a')
            .gsub(/[éèêë]/, 'e')
            .gsub(/[íìîï]/, 'i')
            .gsub(/[óòôöõ]/, 'o')
            .gsub(/[úùûü]/, 'u')
            .gsub(/[ç]/, 'c')
            .gsub(/[^a-z0-9]+/, '-')
            .gsub(/^-|-$/, '')

  # Formatage de la structure de données Jekyll
  organismes[slug] = {
    'title' => nom,
    'descri' => fields['Description'] || '',
    'reco' => fields['Reconnaissance'] || '',
    'champs' => fields['Champs d\'action'] || [],
    'contact' => [
      {
        'name' => 'Site web',
        'link' => fields['Site Web'] || '#',
        'icon' => 'fa-solid fa-globe'
      }
    ].select { |c| c['link'] != '#' }
  }
end

# 4. Écriture dans _data/organismes.yml
FileUtils.mkdir_p('_data')
File.write('_data/organismes.yml', organismes.to_yaml)

puts "Synchronisation réussie : #{organismes.size} organisme(s) exporté(s) vers _data/organismes.yml"