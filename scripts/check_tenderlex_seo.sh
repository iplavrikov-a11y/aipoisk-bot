#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-https://tenderlex.ru}"
BASE_URL="${BASE_URL%/}"

PAGES=(
  "/"
  "/poisk-postavshchikov-po-tz"
  "/poisk-postavshchikov-dlya-tendera"
  "/poisk-proizvoditeley-po-tz"
  "/postavshchiki-dlya-zaprosa-kp"
  "/zapros-kp-po-tz"
  "/analiz-zakupochnoi-dokumentacii"
  "/reestr-minpromtorga-v-zakupkah"
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

printf '[seo-check] base=%s\n' "$BASE_URL"

robots="$(mktemp)"
sitemap="$(mktemp)"
trap 'rm -f "$robots" "$sitemap" "${tmp_files[@]:-}"' EXIT
tmp_files=()

robots_code="$(curl -sS -o "$robots" -w '%{http_code}' "$BASE_URL/robots.txt")"
[[ "$robots_code" == "200" ]] && pass "robots.txt returns 200" || fail "robots.txt returns $robots_code"
check_contains "$robots" 'Sitemap: https://tenderlex\.ru/sitemap\.xml' "robots.txt points to canonical sitemap"
check_contains "$robots" 'Disallow: /cabinet' "robots.txt disallows cabinet"
check_contains "$robots" 'Host: https://tenderlex\.ru' "robots.txt declares Yandex host"

sitemap_code="$(curl -sS -o "$sitemap" -w '%{http_code}' "$BASE_URL/sitemap.xml")"
[[ "$sitemap_code" == "200" ]] && pass "sitemap.xml returns 200" || fail "sitemap.xml returns $sitemap_code"

for path in "${PAGES[@]}"; do
  page_file="$(mktemp)"
  tmp_files+=("$page_file")
  status="$(curl -sS -o "$page_file" -w '%{http_code}' "$BASE_URL$path")"
  [[ "$status" == "200" ]] && pass "$path returns 200" || fail "$path returns $status"
  check_contains "$page_file" '<title>[^<]+' "$path has title"
  check_contains "$page_file" 'rel="canonical"' "$path has canonical"
  if [[ "$path" == "/" ]]; then
    check_contains "$sitemap" "<loc>$BASE_URL</loc>" "$path is in sitemap"
  else
    check_contains "$sitemap" "<loc>$BASE_URL$path</loc>" "$path is in sitemap"
  fi

  if [[ "$path" != "/" ]]; then
    check_contains "$page_file" 'BreadcrumbList' "$path has BreadcrumbList schema"
    check_contains "$page_file" 'Service' "$path has Service schema"
    check_contains "$page_file" 'FAQPage' "$path has FAQPage schema"
  fi
done

www_headers="$(curl -sS -I "https://www.tenderlex.ru/" || true)"
if printf '%s' "$www_headers" | rg -q 'HTTP/[0-9.]+ 301|HTTP/[0-9.]+ 308' && printf '%s' "$www_headers" | rg -q 'Location: https://tenderlex\.ru/'; then
  pass "www redirects to canonical domain"
else
  fail "www redirect to canonical domain"
fi

if (( failures > 0 )); then
  printf '[seo-check] completed with %d failure(s)\n' "$failures" >&2
  exit 1
fi

printf '[seo-check] completed successfully\n'
