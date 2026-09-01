#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 2 ]]; then
  echo "Usage: RESTORE_CONFIRM=<database> $0 <mysql.sql.gz.enc> <database>" >&2
  exit 2
fi

database="$2"
if [[ ! "$database" =~ ^[A-Za-z0-9_]+$ ]]; then
  echo "Invalid database name. Use letters, numbers, or underscores only." >&2
  exit 2
fi
backup_file="$(realpath "$1")"
: "${MYSQL_DEFAULTS_FILE:?MYSQL_DEFAULTS_FILE is required}"
: "${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required}"
: "${BACKUP_PYTHON:=/opt/example-app/current/.venv/bin/python}"
: "${BACKUP_CRYPTO_SCRIPT:=/opt/example-app/current/deploy/scripts/file_crypto.py}"
: "${RESTORE_TMP_ROOT:=/opt/example-app/shared/tmp}"

if [[ "${RESTORE_CONFIRM:-}" != "$database" ]]; then
  echo "Refusing restore. Set RESTORE_CONFIRM=$database after verifying the target." >&2
  exit 1
fi
if [[ ! -f "$backup_file" || "$backup_file" != *.sql.gz.enc ]]; then
  echo "Invalid encrypted MySQL backup: $backup_file" >&2
  exit 1
fi
if [[ ! -r "$MYSQL_DEFAULTS_FILE" || ! -r "$BACKUP_ENCRYPTION_KEY_FILE" ]]; then
  echo "Restore credentials or encryption key are not readable." >&2
  exit 1
fi

printf 'This will import into database %s. Type the database name again: ' "$database" >&2
read -r confirmation
if [[ "$confirmation" != "$database" ]]; then
  echo "Restore cancelled." >&2
  exit 1
fi

mkdir -p "$RESTORE_TMP_ROOT"
decrypted="$(mktemp "$RESTORE_TMP_ROOT/mysql-restore.XXXXXX.sql.gz")"
trap 'rm -f -- "$decrypted"' EXIT
"$BACKUP_PYTHON" "$BACKUP_CRYPTO_SCRIPT" decrypt \
  "$backup_file" "$decrypted" "$BACKUP_ENCRYPTION_KEY_FILE"
gzip -dc "$decrypted" | mysql --defaults-extra-file="$MYSQL_DEFAULTS_FILE" "$database"

echo "MySQL restore completed for $database"
