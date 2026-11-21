#!/bin/bash
set -euo pipefail
export TZ=Asia/Hong_Kong LC_ALL=C
umask 077
ulimit -c 0

backup_dir=${XINSHI_DB_BACKUP_DIR:-/var/backups/xinshi_system/postgres}
container=xinshi_prod_postgres
database=xinshi_system
reserve_bytes=$((50 * 1024**3))
retention_bytes=$((100 * 1024**3))
keep_count=14
pending=
dump_pid=
watch_pid=

log() {
    printf '%s %s\n' "$(date +'%FT%T%:z')" "$*" >&2
}

fail() {
    log "$*"
    exit 1
}

cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n $watch_pid ]]; then
        kill "$watch_pid" 2>/dev/null || true
        wait "$watch_pid" 2>/dev/null || true
    fi
    if [[ -n $dump_pid ]]; then
        kill "$dump_pid" 2>/dev/null || true
        wait "$dump_pid" 2>/dev/null || true
    fi
    if [[ -n $pending ]]; then
        rm -rf -- "$pending"
    fi
    if (( status != 0 )); then
        log "备份任务失败，退出码 $status"
    fi
    exit "$status"
}

available_bytes() {
    df -B1 --output=avail -- "$backup_dir" | awk 'NR == 2 && $1 ~ /^[0-9]+$/ {print $1}'
}

watch_space() {
    local available
    while kill -0 "$dump_pid" 2>/dev/null; do
        available=$(available_bytes) || available=
        if [[ -z $available ]] || (( available < reserve_bytes )); then
            log "备份期间磁盘余量低于 50 GiB，或无法读取余量"
            kill "$dump_pid" 2>/dev/null || true
            return
        fi
        sleep 2
    done
}

prune_backups() {
    local path size total=0 count=0
    local -a paths=() sizes=()
    for path in "$backup_dir"/"$database"-*; do
        [[ ${path##*/} =~ ^xinshi_system-[0-9]{8}-[0-9]{6}\+0800$ ]] || continue
        [[ -d $path && ! -L $path && -f $path/$database.dump && -f $path/SHA256SUMS ]] || continue
        size=$(du -s -B1 -- "$path")
        size=${size%%[[:space:]]*}
        paths+=("$path")
        sizes+=("$size")
        total=$((total + size))
    done
    count=${#paths[@]}
    local index=0
    while (( count > 2 && (count > keep_count || total > retention_bytes) )); do
        rm -rf -- "${paths[index]}"
        log "已清理旧备份 ${paths[index]##*/}"
        total=$((total - sizes[index]))
        index=$((index + 1))
        count=$((count - 1))
    done
    if (( total > retention_bytes )); then
        log "最近两份备份已超过 100 GiB，请复核备份盘容量"
    fi
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
shopt -s nullglob

[[ ! -L $backup_dir ]] || fail "备份目录是符号链接"
install -d -m 0700 -- "$backup_dir"
exec 9>"$backup_dir/.backup.lock"
flock -n 9 || fail "已有备份任务正在执行"

[[ $(docker inspect --type container -f '{{.State.Status}} {{index .Config.Labels "com.docker.compose.project"}}' "$container") == 'running xinshi_prod' ]] ||
    fail "生产 PostgreSQL 容器身份不符或未运行"
pg_exec=(docker exec --user postgres "$container")
connection=(-w -h /var/run/postgresql -U postgres -d "$database")
actual_db=$("${pg_exec[@]}" psql -XAt -v ON_ERROR_STOP=1 "${connection[@]}" -c 'SELECT current_database()')
[[ $actual_db == "$database" ]] || fail "目标数据库不符"

# 持锁清理上一次异常终止留下的临时目录。
for stale in "$backup_dir"/.pending.*; do
    [[ -d $stale && ! -L $stale ]] && rm -rf -- "$stale"
done
available=$(available_bytes)
[[ -n $available ]] && (( available > reserve_bytes )) || fail "备份未开始，磁盘可用空间须大于 50 GiB"
limit=$((available - reserve_bytes))
if (( limit > retention_bytes )); then
    limit=$retention_bytes
fi

name="$database-$(date +'%Y%m%d-%H%M%S%z')"
[[ ! -e $backup_dir/$name ]] || fail "同名备份已存在"
pending=$(mktemp -d -- "$backup_dir/.pending.XXXXXXXX")
archive="$pending/$database.dump"
log "开始导出 $database"

# Docker 客户端写入宿主机文件，文件上限和空间巡检同时生效。
timeout --kill-after=15s 3650s prlimit --fsize="$limit:$limit" -- \
    "${pg_exec[@]}" timeout -k 10 3600 pg_dump "${connection[@]}" \
    --format=custom --lock-wait-timeout=15s >"$archive" 9>&- &
dump_pid=$!
watch_space 9>&- &
watch_pid=$!
dump_status=0
wait "$dump_pid" || dump_status=$?
dump_pid=
kill "$watch_pid" 2>/dev/null || true
wait "$watch_pid" 2>/dev/null || true
watch_pid=
(( dump_status == 0 )) || fail "pg_dump 未完成，退出码 $dump_status"

available=$(available_bytes)
[[ -n $available ]] && (( available >= reserve_bytes )) || fail "导出后磁盘余量不足"
test -s "$archive"
docker exec -i --user postgres "$container" pg_restore --list <"$archive" >/dev/null
(cd -- "$pending" && sha256sum -- "$database.dump" >SHA256SUMS && sha256sum -c SHA256SUMS >/dev/null)
bytes=$(stat -c %s -- "$archive")
mv -T -- "$pending" "$backup_dir/$name"
pending=
log "备份完成 $name，大小 $bytes 字节，耗时 ${SECONDS} 秒"
prune_backups
