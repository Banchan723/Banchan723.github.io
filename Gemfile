source "https://rubygems.org"

# Jekyll 본체 (Actions 클라우드 빌드용. 로컬 설치 불필요)
gem "jekyll", "~> 4.3"

group :jekyll_plugins do
  gem "jekyll-remote-theme"    # minimal-mistakes를 remote_theme로 사용
  gem "jekyll-include-cache"   # minimal-mistakes 필수
  gem "jekyll-feed"
  gem "jekyll-sitemap"
  gem "jekyll-paginate"
end

# Windows/Actions 환경 보조
gem "webrick", "~> 1.8"   # Ruby 3.x 로컬 serve 시 필요
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end
