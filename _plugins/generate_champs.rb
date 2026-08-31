require 'yaml'
require 'fileutils'

# Chemins des dossiers
data_dir = '_data/organismes'
output_dir = '_champs'

unless Dir.exist?(data_dir)
  puts "Erreur : Le dossier #{data_dir} n'existe pas."
  exit
end

# Création du dossier _champs s'il n'existe pas
FileUtils.mkdir_p(output_dir)

all_champs = []

# 1. Lecture de tous les fichiers YAML dans _data/organismes
Dir.glob("#{data_dir}/*.{yml,yaml}").each do |file_path|
  begin
    data = YAML.load_file(file_path)
    
    # Gestion des structures sous forme de liste ou d'objet unique
    items = data.is_a?(Array) ? data : [data]
    
    items.each do |item|
      if item && item['champs'].is_a?(Array)
        all_champs.concat(item['champs'])
      end
    end
  rescue => e
    puts "Erreur lors de la lecture de #{file_path}: #{e.message}"
  end
end

# 2. Dédoublonnage et nettoyage
unique_champs = all_champs.compact.map(&:strip).uniq.sort

puts "Champs trouvés (#{unique_champs.size}) : #{unique_champs.join(', ')}"

# Fonction simple de slugification
def slugify(text)
  text.downcase
      .gsub(/[áàâäã]/, 'a')
      .gsub(/[éèêë]/, 'e')
      .gsub(/[íìîï]/, 'i')
      .gsub(/[óòôöõ]/, 'o')
      .gsub(/[úùûü]/, 'u')
      .gsub(/[ç]/, 'c')
      .gsub(/[^a-z0-9]+/, '-')
      .gsub(/^-|-$/, '')
end

# 3. Génération des fichiers Markdown dans _champs/
unique_champs.each do |champ|
  slug = slugify(champ)
  file_path = File.join(output_dir, "#{slug}.md")

  content = <<~YAML
    ---
    layout: page-single
    title: "Organismes — #{champ}"
    tag_name: "#{champ}"
    ---
  YAML

  File.write(file_path, content)
  puts " [OK] Généré : #{file_path}"
end

puts "\nGénération terminée avec succès !"