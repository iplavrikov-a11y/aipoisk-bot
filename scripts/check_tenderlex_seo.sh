#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://tenderlex.ru}"
BASE_URL="${BASE_URL%/}"
CANONICAL_URL="${CANONICAL_URL:-https://tenderlex.ru}"
CANONICAL_URL="${CANONICAL_URL%/}"
failures=0
tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "$tmp_dir"' EXIT
pass() { printf '[seo-check] OK   %s\n' "$*"; }
fail() { printf '[seo-check] FAIL %s\n' "$*" >&2; failures=$((failures + 1)); }
fetch_to_file() { curl -sS --retry 3 --retry-all-errors --retry-delay 1 --connect-timeout 10 --max-time 30 -o "$2" -w '%{http_code}' "$1"; }

validate_robots() {
  python3 - "$1" "$CANONICAL_URL" <<'PY'
import sys
directives = [line.strip() for line in open(sys.argv[1], encoding="utf-8") if line.strip() and not line.lstrip().startswith("#")]
required = {"User-Agent: *", "Allow: /", "Disallow: /api/", "Disallow: /cabinet", f"Sitemap: {sys.argv[2]}/sitemap.xml"}
if not required.issubset(set(directives)):
    raise SystemExit(f"missing robots directives: {sorted(required - set(directives))}")
if any(line.lower().startswith("host:") for line in directives):
    raise SystemExit("deprecated Host directive found")
PY
}

validate_sitemap() {
  python3 - "$1" "$CANONICAL_URL" <<'PY'
import sys
import xml.etree.ElementTree as ET
namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
root = ET.parse(sys.argv[1]).getroot()
if root.tag != f"{{{namespace}}}urlset": raise SystemExit(f"unexpected sitemap root: {root.tag}")
urls = []
for node in root.findall(f"{{{namespace}}}url"):
    locs = node.findall(f"{{{namespace}}}loc")
    if len(locs) != 1 or not (locs[0].text or "").strip(): raise SystemExit("each sitemap entry needs one non-empty loc")
    url = locs[0].text.strip()
    if not url.startswith(sys.argv[2] + "/") and url != sys.argv[2]: raise SystemExit(f"non-canonical sitemap URL: {url}")
    urls.append(url)
if not urls: raise SystemExit("sitemap is empty")
if len(urls) != len(set(urls)): raise SystemExit("sitemap contains duplicate URLs")
print("\n".join(urls))
PY
}

validate_public_page() {
  python3 - "$1" "$2" <<'PY'
import json, re, sys
from html.parser import HTMLParser
class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.title_depth=self.h1_depth=0; self.title=[]; self.h1=[]; self.description=[]; self.robots=[]; self.canonical=[]; self.json_ld=[]; self.collect_json=False; self.current_json=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs); tag=tag.lower()
        if tag == "title": self.title_depth += 1
        elif tag == "h1": self.h1_depth += 1
        elif tag == "meta" and attrs.get("name", "").lower() == "description": self.description.append(attrs.get("content", ""))
        elif tag == "meta" and attrs.get("name", "").lower() == "robots": self.robots.append(attrs.get("content", ""))
        elif tag == "link" and "canonical" in attrs.get("rel", "").lower().split(): self.canonical.append(attrs.get("href"))
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json": self.collect_json=True; self.current_json=[]
    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag == "title": self.title_depth=max(0,self.title_depth-1)
        elif tag == "h1": self.h1_depth=max(0,self.h1_depth-1)
        elif tag == "script" and self.collect_json: self.json_ld.append("".join(self.current_json)); self.collect_json=False
    def handle_data(self, data):
        if self.title_depth: self.title.append(data)
        if self.h1_depth: self.h1.append(data)
        if self.collect_json: self.current_json.append(data)
page=Parser(); page.feed(open(sys.argv[1],encoding="utf-8").read())
normal=lambda value: re.sub(r"\s+", " ", value).strip()
title,h1=normal("".join(page.title)),normal("".join(page.h1))
if not title or not h1 or len(page.description) != 1 or not normal(page.description[0]): raise SystemExit("title, one non-empty description, and H1 are required")
if re.search(r"tenderlex\s*\|\s*tenderlex", title, re.I): raise SystemExit(f"duplicate brand suffix in title: {title}")
if page.canonical != [sys.argv[2]]: raise SystemExit(f"expected self canonical {[sys.argv[2]]}, got {page.canonical}")
if page.robots != ["index, follow"]: raise SystemExit(f"expected index, follow robots tag, got {page.robots}")
if not page.json_ld: raise SystemExit("at least one JSON-LD document is required")
for schema in page.json_ld: json.loads(schema)
PY
}

check_header() {
  local path="$1" expected="$2" label="$3" headers
  headers="$(curl -sS --retry 3 --retry-all-errors --connect-timeout 10 --max-time 30 -I "$BASE_URL$path")"
  printf '%s\n' "$headers" | tr -d '\r' | rg -qi "^${expected}$" && pass "$label" || fail "$label"
}
check_noindex_page() {
  local path="$1" label="$2" page_file
  page_file="$tmp_dir/$(printf '%s' "$path" | tr '/' '_').html"
  if [[ "$(fetch_to_file "$BASE_URL$path" "$page_file")" == "200" ]] && grep -q '<meta name="robots" content="noindex, nofollow"' "$page_file"; then
    pass "$label"
  else
    fail "$label"
  fi
}
check_redirect() {
  local source="$1" expected="$2" label="$3" result status target
  result="$(curl -sS --retry 3 --retry-all-errors --connect-timeout 10 --max-time 30 -o /dev/null -w '%{http_code}|%{redirect_url}' "$source" || true)"
  status="${result%%|*}"; target="${result#*|}"
  [[ ( "$status" == "301" || "$status" == "308" ) && "$target" == "$expected" ]] && pass "$label" || fail "$label: status=$status target=$target"
}

printf '[seo-check] base=%s\n' "$BASE_URL"
robots="$tmp_dir/robots.txt"
[[ "$(fetch_to_file "$BASE_URL/robots.txt" "$robots")" == "200" ]] && pass "robots.txt returns 200" || fail "robots.txt returns 200"
validate_robots "$robots" && pass "robots.txt has the public crawling contract" || fail "robots.txt has the public crawling contract"

sitemap="$tmp_dir/sitemap.xml"; urls="$tmp_dir/urls.txt"
[[ "$(fetch_to_file "$BASE_URL/sitemap.xml" "$sitemap")" == "200" ]] && pass "sitemap.xml returns 200" || fail "sitemap.xml returns 200"
if validate_sitemap "$sitemap" >"$urls"; then pass "sitemap has $(wc -l < "$urls") unique canonical URLs"; else fail "sitemap has unique canonical URLs"; fi
while IFS= read -r url; do
  page_file="$tmp_dir/page-${RANDOM}.html"; status="$(fetch_to_file "$BASE_URL${url#"$CANONICAL_URL"}" "$page_file")"
  [[ "$status" == "200" ]] && pass "$url returns 200" || { fail "$url returns $status"; continue; }
  validate_public_page "$page_file" "$url" && pass "$url has a complete indexable metadata contract" || fail "$url has a complete indexable metadata contract"
done < "$urls"

cabinet="$tmp_dir/cabinet.html"
[[ "$(fetch_to_file "$BASE_URL/cabinet" "$cabinet")" == "200" ]] && pass "cabinet returns 200" || fail "cabinet returns 200"
grep -q '<meta name="robots" content="noindex, nofollow"' "$cabinet" && pass "cabinet is noindex, nofollow" || fail "cabinet is noindex, nofollow"
check_header "/demo-design" "X-Robots-Tag: noindex, nofollow" "demo-design has an X-Robots-Tag"
check_header "/demo-buttons" "X-Robots-Tag: noindex, nofollow" "demo-buttons has an X-Robots-Tag"
check_noindex_page "/demo-design" "demo-design has a noindex meta tag"
check_noindex_page "/demo-buttons" "demo-buttons has a noindex meta tag"
rg -q 'aggregateRating|ratingValue|ratingCount' site/src && fail "public schema has no unverified aggregate rating" || pass "public schema has no unverified aggregate rating"
check_redirect "http://tenderlex.ru/privacy?seo-check=1" "$CANONICAL_URL/privacy?seo-check=1" "HTTP apex redirects to HTTPS"
check_redirect "https://www.tenderlex.ru/privacy?seo-check=1" "$CANONICAL_URL/privacy?seo-check=1" "HTTPS www redirects to apex"
check_redirect "http://www.tenderlex.ru/privacy?seo-check=1" "$CANONICAL_URL/privacy?seo-check=1" "HTTP www redirects to canonical URL"
(( failures == 0 )) || { printf '[seo-check] completed with %d failure(s)\n' "$failures" >&2; exit 1; }
printf '[seo-check] completed successfully\n'
