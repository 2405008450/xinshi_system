"""只读整理陈佳的六列无表头名单，生成逐行导入计划与核对说明。

不连接或写入数据库。分数不是总体评分；未明确的语言角色和数值意愿保留原文。
包含个人信息的计划和只读目录快照必须保存到仓库外。
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata

SOURCE = "陈佳译员名单"
ROOT = Path(__file__).resolve().parents[1]


def text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text(value))).casefold()


def prepare(rows, catalog, digest):
    languages = {item["label"]: item["id"] for item in catalog["languages"]}
    records = []
    for number, row in rows:
        if len(row) != 6:
            raise ValueError(f"第 {number} 行不是六列，停止生成")
        original_name, account, experience, willingness, score, original_notes = map(text, row)
        if not original_name:
            raise ValueError(f"第 {number} 行姓名栏为空，须人工确认")
        notes, reviews = [], []
        identifiers = re.findall(r"微信号[：:]\s*([A-Za-z0-9_-]+)", original_name + "\n" + original_notes)
        if len(set(identifiers)) > 1:
            raise ValueError(f"第 {number} 行包含多个不同微信号，须人工确认")
        wechat = identifiers[0] if identifiers else None
        # 联系方式仅进入受权限控制的联系字段，绝不复制进公开姓名和备注。
        safe_name = re.sub(r"微信号[：:]\s*[A-Za-z0-9_-]+", "", original_name).strip()
        safe_notes = re.sub(r"微信号[：:]\s*[A-Za-z0-9_-]+", "（微信号已提取至联系字段）", original_notes)
        redbook = re.search(r"小红书\s*id[：:]\s*([^\s）)]+)", safe_notes, re.I)
        other_contact = "小红书ID：" + redbook.group(1) if redbook else None
        if redbook:
            safe_notes = safe_notes[:redbook.start()] + "（小红书ID已提取至联系字段）" + safe_notes[redbook.end():]
        unknown_name = bool(re.search(r"微信号[：:]", original_name))
        native_dutch = "荷兰母语者" in original_name
        name = re.sub(r"[（(]荷兰母语者[）)]", "", safe_name).strip()
        if unknown_name:
            name = f"待确认姓名（陈佳名单第{number}行）"
            notes.append("原表联系人标签：" + safe_name)
            reviews.append("姓名栏只有语言/微信标识，使用明确标注的待确认昵称，不虚构姓名")
        if safe_notes:
            notes.append(safe_notes)
        notes.append(f"原表：{SOURCE}.xlsx，Sheet1 第 {number} 行")
        if score:
            notes.append(f"原表第5列分数：{score}（按用户要求仅保留，不写入总体评分）")
        willingness_value = {"高": "high", "中": "medium", "低": "low"}.get(willingness)
        if willingness and not willingness_value:
            notes.append(f"原表第4列意愿值：{willingness}（未转换为高/中/低）")
            reviews.append("第4列为数值，意愿留空待确认")
        if willingness_value == "high" and re.search(r"不接标注|只接翻译", original_notes):
            reviews.append("高意愿与备注中的不接标注/只接翻译存在冲突，保留原值")
        normalized_account = re.sub(r"\bhr([1-6])\b", lambda match: "HR" + match.group(1), account, flags=re.I)
        if account == "暂时找不到":
            normalized_account = None
            notes.append("原表所在微信：暂时找不到")
        if account == "企微" or "/" in account:
            reviews.append("企微未注明具体HR归属，所在微信保留原文")
        skills = []
        if native_dutch or "自学的荷兰语" in original_notes:
            if "荷兰语" not in languages:
                raise ValueError("现有语言词典缺少荷兰语，停止生成")
            skills.append({"language_id": languages["荷兰语"], "role": "native" if native_dutch else "foreign",
                           "priority": 1, "proficiency": None, "sort_order": 0,
                           "remarks": "原表明确标注荷兰母语者" if native_dutch else "原表备注：自学的荷兰语"})
        elif re.search(r"荷兰语|荷中口译", original_name) or "南非荷兰语" in original_notes:
            reviews.append("有语言线索但母语/外语角色不明确，仅保留原文")
        nickname_only = unknown_name or original_name == "A 认证荷中口译"
        chinese = bool(re.search(r"[\u3400-\u9fff]", name))
        payload = {
            "full_name": name,
            "chinese_name": name if chinese and not nickname_only else None,
            "english_name": name if not chinese and not nickname_only else None,
            "nickname": name if nickname_only else None,
            "wechat": wechat, "other_contact": other_contact,
            "wechat_account": normalized_account or None,
            "registration_source": SOURCE, "annotation_experience": experience or None,
            "annotation_willingness": willingness_value, "overall_score": None,
            "remarks": "\n".join(notes), "status": "standby", "allow_duplicate": True,
            "capabilities": [], "annotation_language_skills": [], "language_skills": skills,
            "certificates": [],
        }
        records.append({"row": number, "idempotency_key": f"chen20260923:{digest}:{number}",
                        "payload": payload, "review_notes": reviews, "duplicate_matches": [],
                        "original_values": [text(v) for v in row]})
    names = Counter(normalize(r["payload"]["full_name"]) for r in records)
    contacts = Counter(normalize(r["payload"]["wechat"]) for r in records if r["payload"]["wechat"])
    for record in records:
        payload = record["payload"]
        if names[normalize(payload["full_name"]) ] > 1:
            record["duplicate_matches"].append({"reason": "表内同名"})
        if payload["wechat"] and contacts[normalize(payload["wechat"])] > 1:
            record["duplicate_matches"].append({"reason": "表内相同微信"})
        for person in catalog["people"]:
            aliases = [person.get(k) for k in ("full_name", "chinese_name", "english_name", "nickname")]
            aliases += person.get("other_names") or []
            reasons = []
            if normalize(payload["full_name"]) in {normalize(value) for value in aliases if value}:
                reasons.append("已有同名/别名")
            if payload["wechat"] and normalize(payload["wechat"]) == normalize(person.get("wechat")):
                reasons.append("已有相同微信")
            if reasons:
                record["duplicate_matches"].append({"id": person["id"], "name": person["full_name"],
                                                    "source": person.get("registration_source"), "reason": "、".join(reasons)})
        record["duplicate_review_required"] = bool(record["duplicate_matches"])
    return {"version": "chen-talents-v1", "source": SOURCE, "source_sha256": digest,
            "status": "prepared_not_imported", "sheet": "Sheet1", "has_header": False,
            "policy": "每行独立新建；同名全部保留，已有档案不覆盖；第5列分数仅保留备注；标注语言留空",
            "records": records,
            "summary": {"records": len(records), "duplicate_review_records": sum(r["duplicate_review_required"] for r in records),
                        "extracted_wechat": sum(bool(r["payload"]["wechat"]) for r in records),
                        "placeholder_names": sum(r["payload"]["full_name"].startswith("待确认姓名") for r in records),
                        "numeric_willingness": sum(r["original_values"][3] not in ("", "高", "中", "低") for r in records),
                        "language_skills": sum(len(r["payload"]["language_skills"]) for r in records)}}


def render_report(plan):
    def cell(value):
        return text(value).replace("|", "／").replace("\n", "；") or "—"
    summary = plan["summary"]
    lines = ["# 陈佳译员名单导入核对", "", "状态：整理完成，未写入数据库。", "",
             f"原表 Sheet1 共 {summary['records']} 行，无表头，第1行也是人员记录。其余两张工作表为空。", "",
             "来源统一为“陈佳译员名单”。第5列分数按用户要求仅保留备注，不写入总体评分。同名全部保留，已有档案不覆盖。", "",
             "| 原列 | 系统字段 | 处理方式 |", "|---|---|---|",
             "| 1 | 姓名/昵称、微信 | 姓名与微信号分离；仅有微信号的联系人使用待确认昵称，不虚构姓名 |",
             "| 2 | 所在微信 | hr1～hr6 规范为 HR1～HR6；企微保留原文，不猜测具体归属 |",
             "| 3 | 标注类经验 | 原样保留有、无及详细经历 |",
             "| 4 | 标注意愿 | 高/中/低映射到对应枚举；数值0/3/5只保留备注 |",
             "| 5 | 备注 | 全部保留，包括0；总体评分留空 |",
             "| 6 | 备注、独立联系字段 | 保留叙述；明确微信号、小红书ID提取到联系字段 |",
             "| 明确语言信息 | 语言情况 | 仅登记明确的荷兰母语者和自学荷兰语；其他语言角色不猜测 |",
             "| 标注语言、专业能力 | 留空 | 不由项目经历自动认定专业能力 |", "",
             f"疑似重复涉及 {summary['duplicate_review_records']} 行；提取微信号 {summary['extracted_wechat']} 条；待确认姓名 {summary['placeholder_names']} 条；数字意愿 {summary['numeric_willingness']} 条。", "",
             "完整原文及联系信息保存在同目录的导入计划.json中。以下预览不重复展示联系账号。", "",
             "## 逐行预览", "", "| Excel行 | 姓名/昵称 | 所在微信 | 意愿 | 第5列分数（仅备注） | 待核对事项 |", "|---|---|---|---|---|---|"]
    for record in plan["records"]:
        p = record["payload"]
        review = list(record["review_notes"])
        if record["duplicate_matches"]:
            review.append("疑似重复，保留新记录并标记核重")
        lines.append("| " + " | ".join(map(cell, [record["row"], p["full_name"], p["wechat_account"],
                     {"high":"高", "medium":"中", "low":"低"}.get(p["annotation_willingness"]),
                     record["original_values"][4], "；".join(review)])) + " |")
    lines += ["", "## 已有档案核重", "", "| Excel行 | 本次姓名/昵称 | 已有姓名 | 匹配原因 | 已有来源 |", "|---|---|---|---|---|"]
    for record in plan["records"]:
        for duplicate in record["duplicate_matches"]:
            lines.append("| " + " | ".join(map(cell, [record["row"], record["payload"]["full_name"],
                         duplicate.get("name"), duplicate["reason"], duplicate.get("source")])) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(ROOT):
        raise ValueError("含个人资料的输出必须位于仓库外")
    import openpyxl
    workbook = openpyxl.load_workbook(args.workbook, read_only=True, data_only=True)
    try:
        rows = [(number, row) for number, row in enumerate(workbook.worksheets[0].values, 1) if any(text(v) for v in row)]
        plan = prepare(rows, json.loads(args.catalog.read_text(encoding="utf-8")),
                       hashlib.sha256(args.workbook.read_bytes()).hexdigest())
    finally:
        workbook.close()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "导入计划.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "字段对应与核对清单.md").write_text(render_report(plan), encoding="utf-8")
    print(json.dumps(plan["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
