source "https://rubygems.org"
# ... (autres commentaires) ...

gem "jekyll", "~> 4.4.1"
gem "minima", "~> 2.5.2"

# Si vous avez des plugins, mettez-les ici !
group :jekyll_plugins do
  gem "jekyll-feed", "~> 0.12"
  gem "jekyll-archives"
  gem 'jekyll-paginate-v2', '~> 3.0' # <-- Déplacé ici
  gem "atproto" # <-- Déplacé ici (atproto n'est pas un plugin Jekyll, mais il peut être utile de le mettre ici si un script de build Jekyll en dépend)
  gem 'activesupport'
end

# ... (autres plateformes et gems) ...
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

gem "wdm", "~> 0.1", :platforms => [:mingw, :x64_mingw, :mswin]
gem "http_parser.rb", "~> 0.6.0", :platforms => [:jruby]
