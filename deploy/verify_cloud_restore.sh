#!/usr/bin/env sh
set -eu

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backup_dir="/home/ubuntu/backups/xinshi_system"
source_inventory="$backup_dir/source_counts.csv"
target_inventory="$backup_dir/target_counts.csv"

sudo docker exec -i xinshi_prod_postgres \
  psql -U postgres -d xinshi_system -q -f - \
  <"$app_dir/deploy/db_inventory.sql" \
  >"$target_inventory"

chmod 600 "$target_inventory"
if ! cmp -s "$source_inventory" "$target_inventory"; then
  diff -u "$source_inventory" "$target_inventory" || true
  exit 1
fi

printf 'inventory_match=yes\n'
printf 'inventory_tables=%s\n' "$(wc -l <"$target_inventory")"
printf 'inventory_rows=%s\n' "$(awk -F, '{sum += $2} END {print sum + 0}' "$target_inventory")"
sha256sum "$source_inventory" "$target_inventory"
sudo docker exec xinshi_prod_postgres \
  psql -U postgres -d xinshi_system -Atc \
  "SELECT 'server_version=' || current_setting('server_version'); SELECT 'db_size=' || pg_size_pretty(pg_database_size(current_database())); SELECT 'public_tables=' || count(*) FROM pg_tables WHERE schemaname='public'; SELECT 'public_views=' || count(*) FROM pg_views WHERE schemaname='public';"
