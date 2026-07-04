#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-./instance}"
UPLOAD_DIR="${UPLOAD_DIR:-$DATA_DIR/uploads}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ -f "$DATA_DIR/site.db" ]; then
  cp "$DATA_DIR/site.db" "$BACKUP_DIR/site-$STAMP.db"
fi

if [ -d "$UPLOAD_DIR" ]; then
  tar -czf "$BACKUP_DIR/uploads-$STAMP.tar.gz" -C "$UPLOAD_DIR" .
fi

echo "Backup completed: $BACKUP_DIR"
