#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 2 ]]; then
  echo "Usage: RESTORE_CONFIRM=media $0 <media-public.tar.gz.enc> <empty-target-root>" >&2
  exit 2
fi

backup_file="$(realpath "$1")"
target_root="$2"
: "${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required}"
: "${BACKUP_PYTHON:=/opt/example-app/current/.venv/bin/python}"
: "${BACKUP_CRYPTO_SCRIPT:=/opt/example-app/current/deploy/scripts/file_crypto.py}"
: "${RESTORE_TMP_ROOT:=/opt/example-app/shared/tmp}"

if [[ "${RESTORE_CONFIRM:-}" != "media" ]]; then
  echo "Refusing restore. Set RESTORE_CONFIRM=media after verifying the target." >&2
  exit 1
fi
if [[ ! -f "$backup_file" || "$backup_file" != *.tar.gz.enc ]]; then
  echo "Invalid encrypted media backup: $backup_file" >&2
  exit 1
fi
if [[ -e "$target_root" && -n "$(find "$target_root" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  echo "Target must be absent or empty: $target_root" >&2
  exit 1
fi

mkdir -p "$target_root" "$RESTORE_TMP_ROOT"
decrypted="$(mktemp "$RESTORE_TMP_ROOT/media-restore.XXXXXX.tar.gz")"
trap 'rm -f -- "$decrypted"' EXIT
"$BACKUP_PYTHON" "$BACKUP_CRYPTO_SCRIPT" decrypt \
  "$backup_file" "$decrypted" "$BACKUP_ENCRYPTION_KEY_FILE"
tar -xzf "$decrypted" -C "$target_root" --no-same-owner --no-same-permissions

echo "Media restore extracted to $target_root. Verify before switching production paths."
