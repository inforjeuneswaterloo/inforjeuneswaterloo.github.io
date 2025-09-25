module Jekyll
  module DomainFilter
    def domain_only(input)
      URI.parse(input).host
    end
  end
end

Liquid::Template.register_filter(Jekyll::DomainFilter)