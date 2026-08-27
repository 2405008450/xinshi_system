"""把三期项目级标注账号数据搬迁到客户级账号资产库。

先执行 ``data/migrations/20260827_annotation_account_library.sql``，核对本脚本输出后，
再执行 ``20260827_annotation_account_library_cleanup.sql``。脚本使用旧记录 UUID 作为
新记录 UUID，因而可以安全重跑；不会自动授予明文查看权限。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from annotation_ops_service import _normalize_url  # noqa: E402
from crypto_utils import decrypt_credential  # noqa: E402
from database import engine  # noqa: E402


def _dict_rows(connection, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(sql), params or {}).mappings().all()]


def _remap_custom_values(values: dict | None, field_map: dict[str, str]) -> dict:
    result: dict[str, Any] = {}
    for key, value in (values or {}).items():
        result[field_map.get(str(key), str(key))] = value
    return result


def migrate(report_path: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "platforms_created": 0,
        "platforms_merged": 0,
        "accounts_created": 0,
        "placeholder_accounts": 0,
        "duplicate_accounts": [],
        "assignments_created": 0,
        "assignments_released_for_conflict": 0,
        "assignment_languages_created": 0,
        "trials_mapped": 0,
        "custom_fields_merged": 0,
        "warnings": [],
        "reveal_permission_granted": False,
    }

    with engine.begin() as connection:
        legacy_platforms = _dict_rows(connection, """
            SELECT p.*, pr.client_id, pr.sub_client_id
            FROM annotation_project_platform p
            JOIN annotation_project pr ON pr.id=p.project_id
            ORDER BY p.created_at, p.id
        """)

        platform_map: dict[str, str] = {}
        platform_by_key: dict[tuple[str | None, str], str] = {}
        next_platform_sequence: dict[str | None, int] = defaultdict(int)
        for row in _dict_rows(connection, "SELECT client_id, COALESCE(MAX(sequence_no), 0) AS max_sequence FROM annotation_platform GROUP BY client_id"):
            next_platform_sequence[str(row["client_id"]) if row["client_id"] else None] = int(row["max_sequence"])

        for legacy in legacy_platforms:
            normalized_url = _normalize_url(legacy["platform_url"])
            client_key = str(legacy["client_id"]) if legacy["client_id"] else None
            key = (client_key, normalized_url)
            target_id = platform_by_key.get(key)
            if target_id is None:
                existing = connection.execute(text("""
                    SELECT id FROM annotation_platform
                    WHERE client_id IS NOT DISTINCT FROM :client_id
                      AND platform_url_normalized=:normalized_url
                """), {"client_id": legacy["client_id"], "normalized_url": normalized_url}).scalar()
                target_id = str(existing) if existing else str(legacy["id"])
                platform_by_key[key] = target_id
                if existing:
                    report["platforms_merged"] += 1
                else:
                    next_platform_sequence[client_key] += 1
                    connection.execute(text("""
                        INSERT INTO annotation_platform(
                            id, client_id, sub_client_id, origin_project_id, platform_name,
                            platform_url, platform_url_normalized, is_active, sequence_no,
                            created_by, created_at, updated_at
                        ) VALUES (
                            :id, :client_id, :sub_client_id, :project_id, :platform_name,
                            :platform_url, :normalized_url, :is_active, :sequence_no,
                            :created_by, :created_at, :updated_at
                        ) ON CONFLICT (id) DO NOTHING
                    """), {
                        **legacy, "id": target_id, "normalized_url": normalized_url,
                        "sequence_no": next_platform_sequence[client_key],
                    })
                    report["platforms_created"] += 1
            else:
                report["platforms_merged"] += 1
            platform_map[str(legacy["id"])] = target_id

        definitions = _dict_rows(connection, """
            SELECT * FROM annotation_custom_field_definition
            WHERE table_code='account'
            ORDER BY created_at, id
        """)
        field_groups: dict[str, list[dict]] = defaultdict(list)
        for definition in definitions:
            field_groups[definition["field_key"]].append(definition)
        field_map: dict[str, str] = {}
        for group in field_groups.values():
            winner = group[0]
            winner_id = str(winner["id"])
            for item in group:
                field_map[str(item["id"])] = winner_id
            loser_ids = [item["id"] for item in group[1:]]
            if loser_ids:
                connection.execute(text("DELETE FROM annotation_custom_field_definition WHERE id = ANY(:ids)"), {"ids": loser_ids})
                report["custom_fields_merged"] += len(loser_ids)
            connection.execute(text("UPDATE annotation_custom_field_definition SET project_id=NULL WHERE id=:id"), {"id": winner["id"]})

        members = _dict_rows(connection, """
            SELECT m.*, p.project_id
            FROM annotation_platform_member m
            JOIN annotation_project_platform p ON p.id=m.platform_id
            ORDER BY m.created_at, m.id
        """)
        credentials = _dict_rows(connection, """
            SELECT * FROM annotation_platform_credential
            ORDER BY member_id,
                     CASE credential_kind WHEN 'primary' THEN 0 ELSE 1 END,
                     is_active DESC, sequence_no, created_at, id
        """)
        credentials_by_member: dict[str, list[dict]] = defaultdict(list)
        for credential in credentials:
            credentials_by_member[str(credential["member_id"])].append(credential)

        account_by_login: dict[tuple[str, str], str] = {}
        for existing in _dict_rows(connection, "SELECT * FROM annotation_platform_account ORDER BY created_at, id"):
            if existing["login_account_normalized"]:
                account_by_login[(str(existing["platform_id"]), existing["login_account_normalized"])] = str(existing["id"])

        next_account_sequence: dict[str, int] = defaultdict(int)
        for row in _dict_rows(connection, "SELECT platform_id, COALESCE(MAX(sequence_no), 0) AS max_sequence FROM annotation_platform_account GROUP BY platform_id"):
            next_account_sequence[str(row["platform_id"])] = int(row["max_sequence"])

        member_main_account: dict[str, str] = {}
        account_registration_statuses: dict[str, list[str]] = defaultdict(list)

        def insert_account(member: dict, credential: dict | None, parent_id: str | None = None) -> str:
            platform_id = platform_map[str(member["platform_id"])]
            proposed_id = str(credential["id"] if credential else member["id"])
            login_account = None
            normalized_login = None
            password = None
            if credential:
                try:
                    login_account = decrypt_credential(
                        credential["login_account_ciphertext"], credential["encryption_key_version"]
                    ).strip()
                    normalized_login = login_account.casefold()
                    password = decrypt_credential(
                        credential["password_ciphertext"], credential["encryption_key_version"]
                    )
                except Exception as exc:
                    report["warnings"].append(f"旧凭据 {credential['id']} 无法解密：{exc}")

            keeper = account_by_login.get((platform_id, normalized_login)) if normalized_login else None
            if keeper and keeper != proposed_id:
                report["duplicate_accounts"].append({
                    "legacy_credential_id": proposed_id,
                    "kept_account_id": keeper,
                    "platform_id": platform_id,
                    "reason": "same_login_account",
                })
                return keeper

            exists = connection.execute(text("SELECT 1 FROM annotation_platform_account WHERE id=:id"), {"id": proposed_id}).scalar()
            if not exists:
                next_account_sequence[platform_id] += 1
                registration_status = member["registration_status"]
                if (not credential or not login_account or not password) and registration_status == "registered":
                    registration_status = "registering"
                    report["warnings"].append(f"成员 {member['id']} 已注册但无可用凭据，迁移为 registering 占位账号")
                nickname = credential.get("display_nickname") if credential and credential["credential_kind"] == "backup" else member["nickname"]
                connection.execute(text("""
                    INSERT INTO annotation_platform_account(
                        id, platform_id, parent_account_id, nickname,
                        login_account, login_account_normalized, password,
                        account_status, registration_status, account_source,
                        custom_values, sequence_no, password_updated_at,
                        created_at, updated_at
                    ) VALUES (
                        :id, :platform_id, :parent_account_id, :nickname,
                        :login_account, :login_account_normalized, :password,
                        'available', :registration_status, 'client_provided',
                        CAST(:custom_values AS jsonb), :sequence_no, :password_updated_at,
                        :created_at, :updated_at
                    )
                """), {
                    "id": proposed_id, "platform_id": platform_id,
                    "parent_account_id": parent_id if parent_id != proposed_id else None,
                    "nickname": nickname, "login_account": login_account,
                    "login_account_normalized": normalized_login, "password": password,
                    "registration_status": registration_status,
                    "custom_values": json.dumps(_remap_custom_values(member["custom_values"], field_map), ensure_ascii=False),
                    "sequence_no": next_account_sequence[platform_id],
                    "password_updated_at": credential.get("password_updated_at") if credential else None,
                    "created_at": credential.get("created_at") if credential else member["created_at"],
                    "updated_at": credential.get("updated_at") if credential else member["updated_at"],
                })
                report["accounts_created"] += 1
                if not credential:
                    report["placeholder_accounts"] += 1
            if normalized_login:
                account_by_login[(platform_id, normalized_login)] = proposed_id
            return proposed_id

        for member in members:
            member_id = str(member["id"])
            items = credentials_by_member.get(member_id, [])
            primaries = [item for item in items if item["credential_kind"] == "primary"]
            backups = [item for item in items if item["credential_kind"] == "backup"]
            if primaries:
                main_id = insert_account(member, primaries[0])
                account_registration_statuses[main_id].append(member["registration_status"])
                for extra in primaries[1:]:
                    extra_id = insert_account(member, extra)
                    account_registration_statuses[extra_id].append(member["registration_status"])
            else:
                main_id = insert_account(member, None)
                account_registration_statuses[main_id].append(member["registration_status"])
            member_main_account[member_id] = main_id
            for backup in backups:
                backup_id = insert_account(member, backup, main_id)
                account_registration_statuses[backup_id].append(member["registration_status"])

        assignment_candidates: dict[str, list[dict]] = defaultdict(list)
        for member in members:
            if member["person_id"]:
                candidate = dict(member)
                candidate["account_id"] = member_main_account[str(member["id"])]
                assignment_candidates[candidate["account_id"]].append(candidate)

        member_assignment: dict[str, str] = {}
        for account_id, candidates in assignment_candidates.items():
            candidates.sort(key=lambda item: (item["created_at"], str(item["id"])))
            candidate_ids = [item["id"] for item in candidates]
            connection.execute(text("""
                UPDATE annotation_account_assignment
                SET released_on=COALESCE(released_on, assigned_on),
                    release_reason=COALESCE(release_reason, 'reassigned')
                WHERE id = ANY(:ids)
            """), {"ids": candidate_ids})
            external_active = connection.execute(text("""
                SELECT id FROM annotation_account_assignment
                WHERE account_id=:account_id AND released_on IS NULL AND NOT (id = ANY(:ids))
                LIMIT 1
            """), {"account_id": account_id, "ids": candidate_ids}).scalar()
            for index, candidate in enumerate(candidates):
                is_latest = index == len(candidates) - 1 and not external_active
                assigned_on = candidate["created_at"].date() if candidate["created_at"] else date.today()
                released_on = None if is_latest else assigned_on
                release_reason = None if is_latest else "reassigned"
                connection.execute(text("""
                    INSERT INTO annotation_account_assignment(
                        id, account_id, person_id, project_id, assigned_on,
                        released_on, release_reason, created_at, updated_at
                    ) VALUES (
                        :id, :account_id, :person_id, :project_id, :assigned_on,
                        :released_on, :release_reason, :created_at, :updated_at
                    ) ON CONFLICT (id) DO UPDATE SET
                        account_id=EXCLUDED.account_id, person_id=EXCLUDED.person_id,
                        project_id=EXCLUDED.project_id, assigned_on=EXCLUDED.assigned_on,
                        released_on=EXCLUDED.released_on, release_reason=EXCLUDED.release_reason,
                        updated_at=EXCLUDED.updated_at
                """), {
                    **candidate, "assigned_on": assigned_on, "released_on": released_on,
                    "release_reason": release_reason,
                })
                member_assignment[str(candidate["id"])] = str(candidate["id"])
                report["assignments_created"] += 1
                if not is_latest:
                    report["assignments_released_for_conflict"] += 1
                languages = _dict_rows(connection, """
                    SELECT language_item_id FROM annotation_platform_member_language
                    WHERE member_id=:member_id
                """, {"member_id": candidate["id"]})
                for language in languages:
                    connection.execute(text("""
                        INSERT INTO annotation_account_assignment_language(assignment_id, language_item_id)
                        VALUES (:assignment_id, :language_item_id) ON CONFLICT DO NOTHING
                    """), {"assignment_id": candidate["id"], **language})
                    report["assignment_languages_created"] += 1

        for account_id, registration_statuses in account_registration_statuses.items():
            active = connection.execute(text("""
                SELECT 1 FROM annotation_account_assignment
                WHERE account_id=:account_id AND released_on IS NULL
            """), {"account_id": account_id}).scalar()
            disabled = "disabled" in registration_statuses
            status = "assigned" if active else "retired" if disabled else "available"
            connection.execute(text("UPDATE annotation_platform_account SET account_status=:status WHERE id=:id"), {"id": account_id, "status": status})

        if member_main_account:
            trial_rows = _dict_rows(connection, """
                SELECT id, legacy_platform_member_id
                FROM annotation_trial_record
                WHERE legacy_platform_member_id IS NOT NULL
            """)
            for trial in trial_rows:
                account_id = member_main_account.get(str(trial["legacy_platform_member_id"]))
                if account_id:
                    connection.execute(text("UPDATE annotation_trial_record SET platform_account_id=:account_id WHERE id=:id"), {"account_id": account_id, "id": trial["id"]})
                    report["trials_mapped"] += 1

        counts = {}
        for table_name in (
            "annotation_project_platform", "annotation_platform", "annotation_platform_member",
            "annotation_platform_credential", "annotation_platform_account",
            "annotation_account_assignment", "annotation_account_assignment_language",
        ):
            counts[table_name] = int(connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar() or 0)
        report["row_counts"] = counts

    rendered = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(rendered)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(rendered + "\n", encoding="utf-8")
    print("提示：annotation_accounts:reveal 未自动授予，请在角色管理中人工配置。")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移标注账号资产库数据")
    parser.add_argument("--report", type=Path, help="可选：将 JSON 对账报告写入指定路径")
    args = parser.parse_args()
    migrate(args.report)


if __name__ == "__main__":
    main()
