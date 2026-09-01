#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${MYSQL_DATABASE:?MYSQL_DATABASE is required}"
: "${BACKUP_ROOT:=/srv/example-app/backups}"
: "${MEDIA_ROOT:=/srv/example-app/media}"
: "${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required}"
: "${BACKUP_PYTHON:=/opt/example-app/current/.venv/bin/python}"
: "${BACKUP_CRYPTO_SCRIPT:=/opt/example-app/current/deploy/scripts/file_crypto.py}"
: "${DAILY_RETENTION_DAYS:=7}"
: "${WEEKLY_RETENTION_DAYS:=35}"

if [[ "$BACKUP_ROOT" != "/srv/example-app/backups" ]]; then
  echo "Refusing unexpected BACKUP_ROOT: $BACKUP_ROOT" >&2
  exit 1
fi
if [[ ! -r "$MYSQL_DEFAULTS_FILE" ]]; then
  echo "MySQL defaults file is not readable: $MYSQL_DEFAULTS_FILE" >&2
  exit 1
fi
if [[ ! -r "$BACKUP_ENCRYPTION_KEY_FILE" ]]; then
  echo "Backup encryption key is not readable: $BACKUP_ENCRYPTION_KEY_FILE" >&2
  exit 1
fi
if [[ ! -d "$MEDIA_ROOT/public" ]]; then
  echo "Media public directory does not exist: $MEDIA_ROOT/public" >&2
  exit 1
fi

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Required command not found: $1" >&2
    exit 1
  }
}
require_command mysqldump
require_command gzip
require_command sha256sum
require_command tar
if [[ ! -x "$BACKUP_PYTHON" || ! -r "$BACKUP_CRYPTO_SCRIPT" ]]; then
  echo "Backup Python or crypto script is unavailable." >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
daily_root="$BACKUP_ROOT/daily"
weekly_root="$BACKUP_ROOT/weekly"
staging_root="$BACKUP_ROOT/.staging"
staging_dir="$staging_root/$stamp"
final_dir="$daily_root/$stamp"

mkdir -p "$daily_root" "$weekly_root" "$staging_dir"
cleanup() {
  rm -rf -- "$staging_dir"
}
trap cleanup EXIT

mysql_plain="$staging_dir/mysql-$MYSQL_DATABASE-$stamp.sql.gz"
mysql_encrypted="$mysql_plain.enc"
media_plain="$staging_dir/media-public-$stamp.tar.gz"
media_encrypted="$media_plain.enc"

mysqldump \
  --defaults-extra-file="$MYSQL_DEFAULTS_FILE" \
  --single-transaction \
  --quick \
  --routines \
  --triggers \
  --events \
  --hex-blob \
  --set-gtid-purged=OFF \
  "$MYSQL_DATABASE" | gzip -9 > "$mysql_plain"

"$BACKUP_PYTHON" "$BACKUP_CRYPTO_SCRIPT" encrypt \
  "$mysql_plain" "$mysql_encrypted" "$BACKUP_ENCRYPTION_KEY_FILE"
rm -f -- "$mysql_plain"

tar -C "$MEDIA_ROOT" -czf "$media_plain" public
"$BACKUP_PYTHON" "$BACKUP_CRYPTO_SCRIPT" encrypt \
  "$media_plain" "$media_encrypted" "$BACKUP_ENCRYPTION_KEY_FILE"
rm -f -- "$media_plain"

(
  cd "$staging_dir"
  sha256sum "$(basename "$mysql_encrypted")" "$(basename "$media_encrypted")" > SHA256SUMS
  printf 'created_at_utc=%s\nmysql_database=%s\nmedia_root=%s\n' \
    "$stamp" "$MYSQL_DATABASE" "$MEDIA_ROOT" > MANIFEST
)

mv -- "$staging_dir" "$final_dir"
trap - EXIT

if [[ "$(date +%u)" == "7" ]]; then
  cp -al -- "$final_dir" "$weekly_root/$stamp"
fi

prune_snapshots() {
  local root="$1"
  local days="$2"
  find "$root" -mindepth 1 -maxdepth 1 -type d -mtime "+$days" -print0 |
    while IFS= read -r -d '' path; do
      case "$path" in
        "$root"/*) rm -rf -- "$path" ;;
        *) echo "Refusing unsafe cleanup path: $path" >&2; exit 1 ;;
      esac
    done
}
prune_snapshots "$daily_root" "$DAILY_RETENTION_DAYS"
prune_snapshots "$weekly_root" "$WEEKLY_RETENTION_DAYS"

echo "Backup completed: $final_dir"
