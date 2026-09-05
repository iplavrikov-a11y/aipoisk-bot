#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://tenderlex.ru}"
BASE_URL="${BASE_URL%/}"
CANONICAL_URL="${CANONICAL_URL:-https://tenderlex.ru}"
CANONICAL_URL="${CANONICAL_URL%/}"

PAGES=(
  "/"
  "/poisk-postavshchikov-po-tz"
  "/poisk-postavshchikov-dlya-tendera"
  "/poisk-proizvoditeley-po-tz"
  "/postavshchiki-dlya-zaprosa-kp"
  "/zapros-kp-po-tz"
  "/analiz-zakupochnoi-dokumentacii"
  "/ocenka-riskov-zakupki"
  "/analiz-rynka-44-fz"
  "/reestr-minpromtorga-v-zakupkah"
  "/legal"
  "/terms"
  "/privacy"
  "/personal-data"
)

SCHEMA_PAGES=(
  "/poisk-postavshchikov-po-tz"
  "/poisk-postavshchikov-dlya-tendera"
  "/poisk-proizvoditeley-po-tz"
  "/postavshchiki-dlya-zaprosa-kp"
  "/zapros-kp-po-tz"
  "/analiz-zakupochnoi-dokumentacii"
  "/ocenka-riskov-zakupki"
  "/analiz-rynka-44-fz"
  "/reestr-minpromtorga-v-zakupkah"
)

declare -A EXPECTED_TITLES=(
  ["/"]="TenderLex - поиск поставщиков и анализ закупок"
  ["/poisk-postavshchikov-po-tz"]="Поиск поставщиков по ТЗ — список для закупки | TenderLex"
  ["/poisk-postavshchikov-dlya-tendera"]="Поиск поставщиков для тендера — проверка рынка до заявки | TenderLex"
  ["/poisk-proizvoditeley-po-tz"]="Поиск производителей по ТЗ — заводы и официальные каналы | TenderLex"
  ["/postavshchiki-dlya-zaprosa-kp"]="Поставщики для запроса КП — первая волна адресатов | TenderLex"
  ["/zapros-kp-po-tz"]="Запрос КП по ТЗ — цены и сроки поставки | TenderLex"
)

declare -A EXPECTED_H1=(
  ["/"]="TenderLex — поиск поставщиков для закупки и снабжения"
  ["/poisk-postavshchikov-po-tz"]="Подобрать поставщиков по ТЗ и спецификации"
  ["/poisk-postavshchikov-dlya-tendera"]="Проверить поставщиков под условия тендера"
  ["/poisk-proizvoditeley-po-tz"]="Найти производителя по ТЗ"
  ["/postavshchiki-dlya-zaprosa-kp"]="Отобрать поставщиков для первого запроса КП"
  ["/zapros-kp-po-tz"]="Подготовить запрос КП по ТЗ"
)

declare -A EXPECTED_DESCRIPTIONS=(
  ["/"]="TenderLex находит компании под закупочную задачу, проверяет контакты, помогает подготовить запрос цены и разобрать условия закупки."
  ["/poisk-postavshchikov-po-tz"]="Передайте ТЗ или спецификацию и получите список производителей, дилеров и поставщиков с контактами, ролью компании и вопросами для первого обращения."
  ["/poisk-postavshchikov-dlya-tendera"]="Передайте извещение или документы тендера и проверьте, какие компании могут закрыть условия, сроки и регион до решения об участии."
  ["/poisk-proizvoditeley-po-tz"]="Передайте ТЗ и получите заводы, бренды и официальные каналы, чтобы подтвердить происхождение, характеристики и возможность поставки."
  ["/postavshchiki-dlya-zaprosa-kp"]="Загрузите уже собранный список компаний и получите первую волну адресатов: без дублей, с каналом связи и вопросами для сопоставимых ответов."
  ["/zapros-kp-po-tz"]="Передайте ТЗ, спецификацию или документы закупки и получите единый запрос КП с позициями, условиями поставки и вопросами для сравнения ответов."
)

failures=0

fail() {
  printf '[seo-check] FAIL %s\n' "$*" >&2
  failures=$((failures + 1))
}

pass() {
  printf '[seo-check] OK   %s\n' "$*"
}

check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if rg -q "$pattern" "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_literal() {
  local file="$1"
  local value="$2"
  local label="$3"
  if rg -Fq "$value" "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_not_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if rg -q "$pattern" "$file"; then
    fail "$label"
  else
    pass "$label"
  fi
}

has_schema_checks() {
  local path="$1"
  local schema_path
  for schema_path in "${SCHEMA_PAGES[@]}"; do
    [[ "$path" == "$schema_path" ]] && return 0
  done
  return 1
}

fetch_to_file() {
  local url="$1"
  local output="$2"
  curl -sS \
    --retry 4 \
    --retry-all-errors \
    --retry-delay 1 \
    --connect-timeout 10 \
    --max-time 30 \
    -o "$output" \
    -w '%{http_code}' \
    "$url"
}

validate_sitemap() {
  local file="$1"

  if python3 - "$file" "$CANONICAL_URL" "${PAGES[@]}" <<'PY'
import sys
import xml.etree.ElementTree as ET

filename, canonical_url, *paths = sys.argv[1:]
namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
root = ET.parse(filename).getroot()
if root.tag != f"{{{namespace}}}urlset":
    raise SystemExit(f"unexpected sitemap root: {root.tag}")

locations = []
for node in root.findall(f"{{{namespace}}}url"):
    locs = node.findall(f"{{{namespace}}}loc")
    if len(locs) != 1 or not (locs[0].text or "").strip():
        raise SystemExit("each sitemap URL must have exactly one non-empty loc")
    locations.append(locs[0].text.strip())

expected = [canonical_url if path == "/" else canonical_url + path for path in paths]
if not expected or len(expected) != len(set(expected)):
    raise SystemExit(f"invalid expected page contract: {len(expected)} URLs")
if len(locations) != len(expected) or len(locations) != len(set(locations)):
    raise SystemExit(f"sitemap must contain {len(expected)} unique URLs, got {len(locations)}")
if set(locations) != set(expected):
    missing = sorted(set(expected) - set(locations))
    extra = sorted(set(locations) - set(expected))
    raise SystemExit(f"missing={missing}; extra={extra}")
PY
  then
    pass "sitemap contains exactly ${#PAGES[@]} unique canonical URLs"
  else
    fail "sitemap contains exactly ${#PAGES[@]} unique canonical URLs"
  fi
}

validate_json_ld() {
  local file="$1"
  local label="$2"
  shift 2
  local required_types
  required_types="$(IFS=,; printf '%s' "$*")"

  if python3 - "$file" "$required_types" <<'PY'
import json
import sys
from html.parser import HTMLParser


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.collecting = False
        self.current = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag.lower() == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.collecting = True
            self.current = []

    def handle_data(self, data):
        if self.collecting:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.collecting:
            self.scripts.append("".join(self.current))
            self.collecting = False
            self.current = []


parser = JsonLdParser()
with open(sys.argv[1], encoding="utf-8") as page:
    parser.feed(page.read())
if not parser.scripts:
    raise SystemExit("no JSON-LD scripts")

documents = [json.loads(script) for script in parser.scripts]
types = set()


def visit(value):
    if isinstance(value, list):
        for item in value:
            visit(item)
    elif isinstance(value, dict):
        schema_type = value.get("@type")
        if isinstance(schema_type, str):
            types.add(schema_type)
        elif isinstance(schema_type, list):
            types.update(item for item in schema_type if isinstance(item, str))
        for item in value.values():
            visit(item)


for document in documents:
    visit(document)
required = [item for item in sys.argv[2].split(",") if item]
missing = [item for item in required if item not in types]
if missing:
    raise SystemExit(f"missing JSON-LD types: {', '.join(missing)}")
PY
  then
    pass "$label has valid JSON-LD${required_types:+ ($required_types)}"
  else
    fail "$label has valid JSON-LD${required_types:+ ($required_types)}"
  fi
}

validate_canonical() {
  local file="$1"
  local expected="$2"
  local label="$3"

  if python3 - "$file" "$expected" <<'PY'
import sys
from html.parser import HTMLParser


class CanonicalParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rel = attrs.get("rel", "").lower().split()
        if tag.lower() == "link" and "canonical" in rel:
            self.values.append(attrs.get("href"))


parser = CanonicalParser()
with open(sys.argv[1], encoding="utf-8") as page:
    parser.feed(page.read())
if parser.values != [sys.argv[2]]:
    raise SystemExit(f"expected {[sys.argv[2]]}, got {parser.values}")
PY
  then
    pass "$label has one exact canonical URL"
  else
    fail "$label has one exact canonical URL"
  fi
}

validate_page_contract() {
  local file="$1"
  local path="$2"

  if python3 - "$file" "${EXPECTED_TITLES[$path]}" "${EXPECTED_H1[$path]}" "${EXPECTED_DESCRIPTIONS[$path]}" <<'PY'
import re
import sys
from html.parser import HTMLParser


def normalized(value):
    return re.sub(r"\s+", " ", value).strip()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_depth = 0
        self.h1_depth = 0
        self.title_parts = []
        self.h1_parts = []
        self.descriptions = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "title":
            self.title_depth += 1
        elif tag == "h1":
            self.h1_depth += 1
        elif tag == "meta" and attrs.get("name", "").lower() == "description":
            self.descriptions.append(attrs.get("content", ""))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)
        elif tag == "h1":
            self.h1_depth = max(0, self.h1_depth - 1)

    def handle_data(self, data):
        if self.title_depth:
            self.title_parts.append(data)
        if self.h1_depth:
            self.h1_parts.append(data)


parser = PageParser()
with open(sys.argv[1], encoding="utf-8") as page:
    parser.feed(page.read())

actual = {
    "title": normalized("".join(parser.title_parts)),
    "h1": normalized("".join(parser.h1_parts)),
    "description": normalized(parser.descriptions[0]) if len(parser.descriptions) == 1 else parser.descriptions,
}
expected = {
    "title": sys.argv[2],
    "h1": sys.argv[3],
    "description": sys.argv[4],
}
if actual != expected:
    raise SystemExit(f"expected={expected}; actual={actual}")
PY
  then
    pass "$path has its unique title, description and H1 contract"
  else
    fail "$path has its unique title, description and H1 contract"
  fi
}

validate_robots() {
  local file="$1"
  if python3 - "$file" "$CANONICAL_URL" <<'PY'
import sys

with open(sys.argv[1], encoding="utf-8") as robots:
    directives = [line.strip() for line in robots if line.strip() and not line.lstrip().startswith("#")]
expected = {
    "User-Agent: *",
    "Allow: /",
    "Disallow: /api/",
    "Disallow: /cabinet",
    f"Sitemap: {sys.argv[2]}/sitemap.xml",
}
if len(directives) != len(expected) or set(directives) != expected:
    raise SystemExit(f"unexpected robots directives: {directives}")
PY
  then
    pass "robots.txt has the exact public crawling contract"
  else
    fail "robots.txt has the exact public crawling contract"
  fi
}

check_redirect() {
  local source="$1"
  local expected="$2"
  local label="$3"
  local result status target

  result="$(curl -sS --retry 4 --retry-all-errors --retry-delay 1 --connect-timeout 10 --max-time 30 -o /dev/null -w '%{http_code}|%{redirect_url}' "$source" || true)"
  status="${result%%|*}"
  target="${result#*|}"
  if [[ "$status" == "301" || "$status" == "308" ]] && [[ "$target" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label: status=$status target=$target"
  fi
}

printf '[seo-check] base=%s\n' "$BASE_URL"

robots="$(mktemp)"
sitemap="$(mktemp)"
trap 'rm -f "$robots" "$sitemap" "${tmp_files[@]:-}"' EXIT
tmp_files=()

robots_code="$(fetch_to_file "$BASE_URL/robots.txt" "$robots")"
[[ "$robots_code" == "200" ]] && pass "robots.txt returns 200" || fail "robots.txt returns $robots_code"
check_literal "$robots" "Sitemap: $CANONICAL_URL/sitemap.xml" "robots.txt points to canonical sitemap"
check_contains "$robots" 'Disallow: /cabinet' "robots.txt disallows cabinet"
check_not_contains "$robots" '^Host:' "robots.txt omits deprecated Host directive"
validate_robots "$robots"
robots_content_type="$(curl -sS --retry 4 --retry-all-errors --retry-delay 1 -o /dev/null -w '%{content_type}' "$BASE_URL/robots.txt")"
[[ "$robots_content_type" == text/plain* ]] && pass "robots.txt has text/plain content type" || fail "robots.txt content type is $robots_content_type"

sitemap_code="$(fetch_to_file "$BASE_URL/sitemap.xml" "$sitemap")"
[[ "$sitemap_code" == "200" ]] && pass "sitemap.xml returns 200" || fail "sitemap.xml returns $sitemap_code"
validate_sitemap "$sitemap"

for path in "${PAGES[@]}"; do
  page_file="$(mktemp)"
  tmp_files+=("$page_file")
  status="$(fetch_to_file "$BASE_URL$path" "$page_file")"
  [[ "$status" == "200" ]] && pass "$path returns 200" || fail "$path returns $status"
  check_contains "$page_file" '<title>[^<]+' "$path has title"
  expected_canonical="$CANONICAL_URL"
  [[ "$path" == "/" ]] || expected_canonical="$CANONICAL_URL$path"
  validate_canonical "$page_file" "$expected_canonical" "$path"
  if [[ -n "${EXPECTED_TITLES[$path]:-}" ]]; then
    validate_page_contract "$page_file" "$path"
  fi

  if has_schema_checks "$path"; then
    validate_json_ld "$page_file" "$path" BreadcrumbList Service FAQPage
  elif rg -q 'application/ld\+json' "$page_file"; then
    validate_json_ld "$page_file" "$path"
  fi
done

check_redirect \
  "http://tenderlex.ru/privacy?seo-check=1" \
  "$CANONICAL_URL/privacy?seo-check=1" \
  "HTTP apex redirects to HTTPS and preserves path/query"
check_redirect \
  "https://www.tenderlex.ru/privacy?seo-check=1" \
  "$CANONICAL_URL/privacy?seo-check=1" \
  "HTTPS www redirects to apex and preserves path/query"
check_redirect \
  "http://www.tenderlex.ru/privacy?seo-check=1" \
  "$CANONICAL_URL/privacy?seo-check=1" \
  "HTTP www redirects directly to canonical URL"

if (( failures > 0 )); then
  printf '[seo-check] completed with %d failure(s)\n' "$failures" >&2
  exit 1
fi

printf '[seo-check] completed successfully\n'
