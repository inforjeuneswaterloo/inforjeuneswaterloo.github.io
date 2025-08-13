# _plugins/custom_filters.rb
# _plugins/custom_filters.rb
require 'active_support/inflector'

module Jekyll
  module CustomFilters
    def custom_slugify(input)
      # Transliterate converts special characters (e.g. 'é' to 'e')
      # parameterize converts the string to a URL-friendly format
      ActiveSupport::Inflector.transliterate(input.to_s).parameterize
    end
  end
end

Liquid::Template.register_filter(Jekyll::CustomFilters)