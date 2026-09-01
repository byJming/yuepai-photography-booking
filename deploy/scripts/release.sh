#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <release-source-root> [release-id]" >&2
  exit 2
fi
release_id="${2:-$(date -u +%Y%m%dT%H%M%SZ)}"
if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]; then
  echo "Invalid release ID. Use 1-64 letters, numbers, dots, underscores, or hyphens." >&2
  exit 2
fi
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this release helper as root." >&2
  exit 1
fi

source_root="$(realpath "$1")"
release_root="/opt/example-app/releases"
target="$release_root/$release_id"
current_link="/opt/example-app/current"
previous_link="/opt/example-app/previous"
python_bin="${PYTHON_BIN:-python3.11}"

for required in backend admin-web/dist deploy; do
  if [[ ! -e "$source_root/$required" ]]; then
    echo "Release source is missing: $source_root/$required" >&2
    exit 1
  fi
done
if [[ -e "$target" ]]; then
  echo "Release already exists: $target" >&2
  exit 1
fi
command -v rsync >/dev/null 2>&1 || { echo "rsync is required." >&2; exit 1; }
command -v "$python_bin" >/dev/null 2>&1 || { echo "$python_bin is required." >&2; exit 1; }

install -d -m 0755 /opt/example-app "$release_root"
install -d -o example-app -g example-app -m 0750 /opt/example-app/shared /opt/example-app/shared/tmp /opt/example-app/shared/logs
install -d -o example-app -g example-app -m 0750 /srv/example-app/media/public /srv/example-app/media/tmp /srv/example-app/backups
install -d -m 0755 "$target"

rsync -a --delete \
  --exclude '.venv/' --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '.mypy_cache/' \
  "$source_root/backend/" "$target/backend/"
rsync -a --delete "$source_root/admin-web/dist/" "$target/admin-web-dist/"
rsync -a --delete "$source_root/deploy/" "$target/deploy/"

"$python_bin" -m venv "$target/.venv"
"$target/.venv/bin/python" -m pip install --upgrade pip
"$target/.venv/bin/pip" install --require-hashes -r "$target/backend/requirements.lock"
"$target/.venv/bin/pip" install --no-deps "$target/backend"

set -a
# shellcheck disable=SC1091
source /etc/example-app/yuepai.env
set +a
(
  cd "$target/backend"
  "$target/.venv/bin/python" -c 'from app.core.config import get_settings; get_settings(); print("configuration ok")'
  "$target/.venv/bin/alembic" upgrade head
)

old_current=""
if [[ -L "$current_link" ]]; then
  old_current="$(readlink -f "$current_link")"
  systemctl start yuepai-backup.service
  systemctl is-failed --quiet yuepai-backup.service && {
    echo "Pre-release backup failed." >&2
    exit 1
  }
fi

chown -R root:yuepai "$target"
chmod 0755 "$target"
find "$target/backend" "$target/.venv" "$target/deploy" -type d -exec chmod 0750 {} +
find "$target/admin-web-dist" -type d -exec chmod 0755 {} +
find "$target/deploy/scripts" -type f -name '*.sh' -exec chmod 0750 {} +
find "$target/admin-web-dist" -type f -exec chmod 0644 {} +

next_link="/opt/example-app/.current-$release_id"
ln -s "$target" "$next_link"
mv -Tf "$next_link" "$current_link"
if [[ -n "$old_current" ]]; then
  ln -sfn "$old_current" "$previous_link"
fi

systemctl restart yuepai-api.service
if ! "$current_link/deploy/scripts/healthcheck.sh" http://127.0.0.1:8100; then
  echo "New release failed health checks." >&2
  if [[ -n "$old_current" ]]; then
    ln -sfn "$old_current" "$current_link"
    systemctl restart yuepai-api.service
  fi
  exit 1
fi

systemctl reload nginx
echo "Release activated: $target"
