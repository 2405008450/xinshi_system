#!/usr/bin/env sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_env="$app_dir/.source-db.env"
backup_dir="/home/ubuntu/backups/xinshi_system"
inventory_file="$backup_dir/source_counts.csv"
dump_file=$(find "$backup_dir" -maxdepth 1 -type f -name 'source_xinshi_system_lan_*.dump' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)

test -n "$dump_file"
sudo docker run --rm \
  -v "$backup_dir:/backup:ro" \
  postgres:18-alpine \
  pg_restore --list "/backup/$(basename "$dump_file")" >/dev/null

sudo docker run --rm \
  --network host \
  --env-file "$source_env" \
  -v "$app_dir/deploy:/sql:ro" \
  postgres:18-alpine \
  sh -ec '
    export PGPASSWORD="$DB_PASSWORD"
    psql \
      -h 127.0.0.1 \
      -p 55432 \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -q \
      -f /sql/db_inventory.sql
  ' >"$inventory_file"

chmod 600 "$inventory_file"
printf 'dump_bytes=%s\n' "$(stat -c %s "$dump_file")"
printf 'inventory_tables=%s\n' "$(wc -l <"$inventory_file")"
printf 'inventory_rows=%s\n' "$(awk -F, '{sum += $2} END {print sum + 0}' "$inventory_file")"
sha256sum "$inventory_file"
