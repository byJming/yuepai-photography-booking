#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this rollback helper as root." >&2
  exit 1
fi

current_link="/opt/example-app/current"
previous_link="/opt/example-app/previous"
if [[ ! -L "$previous_link" ]]; then
  echo "No previous release is recorded." >&2
  exit 1
fi

current_target="$(readlink -f "$current_link")"
rollback_target="$(readlink -f "$previous_link")"
case "$rollback_target" in
  /opt/example-app/releases/*) ;;
  *) echo "Refusing unexpected rollback target: $rollback_target" >&2; exit 1 ;;
esac

ln -sfn "$rollback_target" "$current_link"
ln -sfn "$current_target" "$previous_link"
systemctl restart yuepai-api.service

if ! "$current_link/deploy/scripts/healthcheck.sh" http://127.0.0.1:8100; then
  echo "Rollback target failed health checks; investigate immediately." >&2
  exit 1
fi

systemctl reload nginx
echo "Rolled back to: $rollback_target"
echo "Database downgrade was not executed."
