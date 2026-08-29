#!/usr/bin/env sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_env="$app_dir/.source-db.env"
backup_dir="/home/ubuntu/backups/xinshi_system"
timestamp=$(date +%Y%m%d_%H%M%S)
dump_name="source_xinshi_system_lan_${timestamp}.dump"

test -f "$source_env"
install -d -m 750 "$backup_dir"

sudo docker run --rm \
  --network host \
  --env-file "$source_env" \
  -v "$backup_dir:/backup" \
  postgres:18-alpine \
  sh -ec '
    export PGPASSWORD="$DB_PASSWORD"
    pg_isready -h 127.0.0.1 -p 55432 -U "$DB_USER" -d "$DB_NAME"
    pg_dump \
      -h 127.0.0.1 \
      -p 55432 \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      --format=custom \
      --compress=9 \
      --no-owner \
      --no-privileges \
      --file="/backup/'"$dump_name"'"
  '

sudo chown "$(id -u):$(id -g)" "$backup_dir/$dump_name"
chmod 600 "$backup_dir/$dump_name"
sha256sum "$backup_dir/$dump_name"
