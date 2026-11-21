#!/bin/bash
set -euo pipefail

script=$(cd -- "$(dirname -- "$0")" && pwd)/backup_cloud_db.sh
base=$(mktemp -d)
trap 'rm -rf -- "$base"' EXIT
export XINSHI_DB_BACKUP_DIR="$base/backups"
export PATH="$base/bin:$PATH"
mkdir -- "$base/bin"

cat >"$base/bin/docker" <<'EOF'
#!/bin/bash
case " $* " in
    *' inspect '*) echo 'running xinshi_prod';;
    *' psql '*) printf '%s\n' "${MOCK_DB:-xinshi_system}";;
    *' pg_dump '*)
        case ${MOCK_DUMP:-success} in
            fail) printf partial; exit 7;;
            large) head -c 8192 /dev/zero;;
            *) printf synthetic-data;;
        esac;;
    *' pg_restore '*) cat >/dev/null; [[ ${MOCK_RESTORE:-success} == success ]];;
    *) exit 98;;
esac
EOF
cat >"$base/bin/df" <<'EOF'
#!/bin/bash
printf 'Avail\n%s\n' "${MOCK_AVAIL:-197568495616}"
EOF
chmod +x "$base/bin/"*

shopt -s nullglob
bash "$script"
archives=("$XINSHI_DB_BACKUP_DIR"/xinshi_system-*)
[[ ${#archives[@]} == 1 ]]
(cd "${archives[0]}" && sha256sum -c SHA256SUMS)

expect_failure() {
    local message=$1 output
    shift
    if output=$("$@" 2>&1) || [[ $output != *"$message"* ]]; then
        printf '预期失败原因：%s\n实际输出：\n%s\n' "$message" "$output" >&2
        exit 1
    fi
    local partials=("$XINSHI_DB_BACKUP_DIR"/.pending.*)
    [[ ${#partials[@]} == 0 && -s ${archives[0]}/xinshi_system.dump ]]
}

sleep 1
expect_failure 'pg_dump 未完成，退出码 7' env MOCK_DUMP=fail bash "$script"
expect_failure '备份任务失败' env MOCK_RESTORE=fail bash "$script"
expect_failure '磁盘可用空间须大于' env MOCK_AVAIL=53687091200 bash "$script"
expect_failure 'pg_dump 未完成' env MOCK_AVAIL=53687091232 MOCK_DUMP=large bash "$script"
expect_failure '目标数据库不符' env MOCK_DB=other bash "$script"
(
    exec 8<"$XINSHI_DB_BACKUP_DIR/.backup.lock"
    flock -n 8
    expect_failure '已有备份任务正在执行' bash "$script"
)

for day in {01..14}; do
    target="$XINSHI_DB_BACKUP_DIR/xinshi_system-200001${day}-030000+0800"
    mkdir -- "$target"
    printf old >"$target/xinshi_system.dump"
    (cd "$target" && sha256sum xinshi_system.dump >SHA256SUMS)
done
mkdir -- "$XINSHI_DB_BACKUP_DIR/manual-release"
bash "$script"
remaining=("$XINSHI_DB_BACKUP_DIR"/xinshi_system-*)
[[ ${#remaining[@]} == 14 && -d $XINSHI_DB_BACKUP_DIR/manual-release ]]
[[ ! -e $XINSHI_DB_BACKUP_DIR/xinshi_system-20000102-030000+0800 ]]
printf '备份流程检查通过\n'
