#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/apps/xinshi_system
test "$(git rev-parse HEAD)" = ecc47e6a100512ca195fc861227c202814410724
backup=/home/ubuntu/backups/xinshi_system/releases/20261015-205147
db=xinshi_schema_verify_ecc47e6
cleanup() { sudo docker exec xinshi_prod_postgres dropdb -U postgres --if-exists "$db"; }
sudo docker exec xinshi_prod_postgres createdb -U postgres "$db"
trap cleanup EXIT
sudo docker exec xinshi_prod_postgres psql -v ON_ERROR_STOP=1 -U postgres -d "$db" -c 'CREATE TABLE app_user (id uuid PRIMARY KEY);'
sudo docker exec -i xinshi_prod_postgres psql -v ON_ERROR_STOP=1 -U postgres -d "$db" < data/migrations/20261018_project_notices.sql
sudo docker exec -i xinshi_prod_postgres psql -v ON_ERROR_STOP=1 -U postgres -d "$db" -At < "$backup/schema_check.sql" > "$backup/expected_schema.txt"
sudo docker exec -i xinshi_prod_postgres psql -v ON_ERROR_STOP=1 -U postgres -d xinshi_system -At < "$backup/schema_check.sql" > "$backup/actual_schema.txt"
diff -u "$backup/expected_schema.txt" "$backup/actual_schema.txt"
sudo docker exec xinshi_prod_postgres psql -U postgres -d xinshi_system -Atc "SELECT convalidated,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='resource_request'::regclass AND conname='ck_resource_request_demand_status';"
echo NOTICE_SCHEMA_MATCHES_LATEST_SQL
