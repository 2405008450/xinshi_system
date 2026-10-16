#!/usr/bin/env bash
set -Eeuo pipefail
cd /home/ubuntu/apps/xinshi_system
backup=/home/ubuntu/backups/xinshi_system/releases/20261015-205147
dc() { sudo /usr/local/bin/docker-compose --env-file .env -f deploy/docker-compose.cloud.yml -f deploy/docker-compose.cloud.local.yml "$@"; }
rollback() {
    trap - ERR
    echo RELEASE_FAILED_RESTORING_PREVIOUS_IMAGES
    sudo docker image tag xinshi_prod-backend:rollback-20261015-205147 xinshi_prod-backend:latest
    sudo docker image tag xinshi_prod-frontend:rollback-20261015-205147 xinshi_prod-frontend:latest
    cp "$backup/docker-compose.cloud.local.yml" deploy/docker-compose.cloud.local.yml
    dc up -d --no-deps --force-recreate backend frontend https_gateway
    exit 1
}
test "$(hostname)" = VM-0-9-ubuntu
test "$(git rev-parse HEAD)" = ecc47e6a100512ca195fc861227c202814410724
test "$(sudo docker exec xinshi_prod_postgres psql -U postgres -d xinshi_system -Atc 'SELECT current_database()')" = xinshi_system
trap rollback ERR
dc stop https_gateway frontend
dc up -d --no-deps --force-recreate backend
healthy=false
for i in $(seq 1 15); do
    if sudo docker exec xinshi_prod_backend python -c 'import urllib.request,json; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/db",timeout=2))["status"]=="ok"' 2>/dev/null; then healthy=true; break; fi
    sleep 2
done
test "$healthy" = true
dc up -d --no-deps --force-recreate frontend
healthy=false
for i in $(seq 1 10); do
    if curl -fsS --max-time 2 http://127.0.0.1:3000/login | grep -q index-BfU3lXX7.js; then healthy=true; break; fi
    sleep 2
done
test "$healthy" = true
dc up -d --no-deps --force-recreate https_gateway
healthy=false
for i in $(seq 1 10); do
    if curl -fsS --max-time 3 --resolve www.oa.xinshify.com.cn:443:127.0.0.1 https://www.oa.xinshify.com.cn/api/health/db | grep -q '"status":"ok"'; then healthy=true; break; fi
    sleep 2
done
test "$healthy" = true
echo RELEASE_ECC47E6_HEALTHY
