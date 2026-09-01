#!/usr/bin/env bash
set -Eeuo pipefail

base_url="${1:-http://127.0.0.1:8100}"
curl --fail --silent --show-error --max-time 5 "$base_url/health/live" >/dev/null
curl --fail --silent --show-error --max-time 8 "$base_url/health/ready" >/dev/null
echo "Yuepai health checks passed: $base_url"
