#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:3201}"

curl -fsS "$BASE_URL/googlechat/health" | python3 -m json.tool

curl -fsS \
  -H 'Content-Type: application/json' \
  -d @tests/fixtures/googlechat_message.json \
  "$BASE_URL/googlechat/" | python3 -m json.tool
