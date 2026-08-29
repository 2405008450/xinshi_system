#!/usr/bin/env sh
set -eu
export LC_ALL=C

app_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
backup_dir="/home/ubuntu/backups/xinshi_system"
source_inventory="$backup_dir/source_counts.csv"
target_inventory="$backup_dir/post_migration_counts.csv"
source_inventory_sorted="$backup_dir/source_counts.sorted.csv"
target_inventory_sorted="$backup_dir/post_migration_counts.sorted.csv"
source_names="$backup_dir/source_table_names.txt"
target_names="$backup_dir/post_migration_table_names.txt"
mismatches="$backup_dir/post_migration_mismatches.csv"

sudo docker exec -i xinshi_prod_postgres \
  psql -U postgres -d xinshi_system -q -f - \
  <"$app_dir/deploy/db_inventory.sql" \
  >"$target_inventory"

LC_ALL=C sort -t, -k1,1 "$source_inventory" >"$source_inventory_sorted"
LC_ALL=C sort -t, -k1,1 "$target_inventory" >"$target_inventory_sorted"
join -t, -1 1 -2 1 "$source_inventory_sorted" "$target_inventory_sorted" \
  | awk -F, '$2 != $3' >"$mismatches"
test ! -s "$mismatches"

cut -d, -f1 "$source_inventory_sorted" >"$source_names"
cut -d, -f1 "$target_inventory_sorted" >"$target_names"
test -z "$(comm -23 "$source_names" "$target_names")"

chmod 600 "$target_inventory" "$source_inventory_sorted" "$target_inventory_sorted" "$source_names" "$target_names" "$mismatches"
printf 'source_tables_unchanged=yes\n'
printf 'post_migration_tables=%s\n' "$(wc -l <"$target_inventory")"
printf 'post_migration_rows=%s\n' "$(awk -F, '{sum += $2} END {print sum + 0}' "$target_inventory")"
printf 'added_tables:\n'
comm -13 "$source_names" "$target_names"
sha256sum "$target_inventory"
