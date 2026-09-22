"""只读解析资源整合问卷，生成可复核的导入计划，不连接数据库。

目录快照包含 languages(id/code/label)、aliases(language_id/alias)、people。
输出含个人资料，应保存到仓库外；工作簿中的文字仅作为数据处理。
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5


SOURCE = "2609资源整合行动"
EMPTY = {"", "(空)", "（空）", "无", "none", "n/a", "no", "-", ".", "x", "跳过", "不会"}
COLUMN_NAMES = ["姓名", "微信", "性别", "年龄", "国籍", "民族", "主要成长地", "目前所在地",
                "最高学历", "毕业院校", "所学专业", "职业状态", "方言/少数民族语", "方言熟悉程度",
                "母语", "第一外语", "其他外语", "有无外语证书", "证书及等级", "有无标注经验",
                "标注项目经验", "简历链接"]


def clean(value):
    value = html.unescape(str(value)).strip() if value is not None else ""
    return "" if value.casefold() in EMPTY else value


def key(value):
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", value).casefold())


# 只记录语言本身的同义词；不根据国籍推断母语，也不将泛称强制匹配到地区变体。
LANGUAGE_ALIASES = {
    "中文（简体）": "中文|汉语|汉话|Chinese|Simplified Chinese|Chinese Language|中文普通话",
    "普通话": "普通话|普通話|国语|Mandarin|Chinese Mandarin|汉语普通话|标准普通话",
    "英语": "English|英文|英語|英语|Eng|engl|enlish|英语yingyu|英文语|Native English",
    "法语": "French|法语|法文",
    "德语": "German|德语|德文",
    "德语（德国）": "German (Germany)|德语（德国）",
    "西班牙语": "Spanish|西语|西班牙语",
    "西班牙语（欧洲）": "欧洲西班牙语|Spanish (Spain)",
    "西班牙语（拉丁美洲）": "Mexican Spanish|拉美西语|Spanish (Latin America)",
    "葡萄牙语": "Portuguese|葡语|葡萄牙语",
    "葡萄牙语（巴西）": "巴西葡萄牙语|Brazilian Portuguese",
    "阿拉伯语": "Arabic|阿拉伯语|阿语|arabi",
    "日语": "Japanese|日本语|日语|日文",
    "韩语": "Korean|韩国语|韩语|朝鲜语|朝鲜语/韩语",
    "缅甸语": "Burmese|Burmses|缅甸语|缅语",
    "印度尼西亚语": "Indonesian|印尼语|印度尼西亚语|Bahasa Indonesia|Indonesia",
    "高棉语": "Khmer|高棉语|柬语|柬埔寨语",
    "马来语": "Malay|马来语|Bahasa Malaysia|Bahasa Melayu|malays",
    "波斯语": "Persian|Farsi|波斯语",
    "孟加拉语": "Bengali|Bangla|bangle|孟加拉语",
    "哈萨克语": "Kazakh|哈萨克语",
    "粤语": "Cantonese|粤语|粵語|广东话|广州话|广式粤语|广府粤语|白话",
    "闽南语": "Hokkien|闽南语|闽南话|闽南|福建话",
    "客家话": "Hakka|客家话",
    "上海话": "上海话|沪语",
    "潮汕话": "潮汕话|潮州话|潮州|潮汕方言",
    "爪哇语": "Javanese|Java|爪哇语|Javanese language",
    "菲律宾语": "Filipino|Tagalog|菲律宾语|Filipino/ Tagalog",
    "斯瓦希里语": "Swahili|swahili|斯瓦希里语",
    "南非荷兰语": "Afrikaans|南非荷兰语",
    "泰卢固语": "Telugu|泰卢固语",
    "阿塞拜疆语": "Azerbaijan|Azerbaijani|阿塞拜疆语",
    "普什图语": "Pashto|普什图语",
    "索马里语": "Somali|索马里语",
    "伊博语": "Igbo|Igbo Language|Igbo Languages|伊博语",
    "约鲁巴语": "Yoruba|约鲁巴语",
    "卢干达语": "Luganda|卢干达语",
    "白俄罗斯语": "Belarusian|白俄罗斯语",
    "傣语": "Dai language|傣语|傣族语",
    "掸语": "Shan|掸语",
    "维吾尔语": "Uyghur|维语|维吾尔语",
    "吉尔吉斯语": "Kyrgyz|吉尔吉斯语|吉尔吉斯古",
    "土库曼语": "Turkmen|土库曼语|土库曼",
    "希利盖农语": "Hiligaynon|希利盖农语",
    "伊洛卡诺语": "Ilocano|伊洛卡诺语",
    "豪萨语": "Hausa|豪萨语",
    "塔吉克语": "Tajik|塔吉克语",
}


class LanguageResolver:
    def __init__(self, catalog):
        self.by_label = {x["label"]: x["id"] for x in catalog["languages"]}
        self.by_id = {x["id"]: x["label"] for x in catalog["languages"]}
        self.aliases = defaultdict(set)
        for language in catalog["languages"]:
            self.aliases[key(language["label"])].add(language["label"])
        for alias in catalog["aliases"]:
            # 短缩写和国家名不能用于正文里的模糊匹配。
            if len(key(alias["alias"])) >= 2:
                self.aliases[key(alias["alias"])].add(self.by_id[alias["language_id"]])
        for label, aliases in LANGUAGE_ALIASES.items():
            for alias in (label + "|" + aliases).split("|"):
                self.aliases[key(alias)] = {label}
        self.new_languages = {}

    def resolve(self, raw):
        """整项匹配优先；组合值按最长别名匹配，未识别内容仍在原始备注中保留。"""
        if not clean(raw):
            return [], []
        normalized = key(raw)
        original = unicodedata.normalize("NFKC", raw).casefold()
        positions = [i for i, char in enumerate(original) if re.match(r"[^\W_]", char)]
        if normalized in self.aliases and len(self.aliases[normalized]) == 1:
            labels = list(self.aliases[normalized])
            remainder = ""
        elif re.search(r"\bteam\b|母语是|阿拉伯语为母语", raw, re.I):
            # 团队能力及跨角色叙述需人工确认，不能当成本人该角色的语言。
            return [], [raw]
        else:
            labels, spans = [], []
            for alias, candidates in sorted(self.aliases.items(), key=lambda x: -len(x[0])):
                if len(candidates) != 1 or len(alias) < 2:
                    continue
                if alias.isascii() and len(alias) < 4:
                    continue
                for match in re.finditer(re.escape(alias), normalized):
                    start, end = match.span()
                    if any(start < b and end > a for a, b in spans):
                        continue
                    if alias.isascii():
                        left, right = positions[start], positions[end-1] + 1
                        if ((left and original[left-1].isascii() and original[left-1].isalpha()) or
                                (right < len(original) and original[right].isascii() and original[right].isalpha())):
                            continue
                    spans.append((start, end))
                    labels.append((start, next(iter(candidates))))
            labels = [label for _, label in sorted(labels)]
            remainder = "".join(ch for i, ch in enumerate(normalized) if not any(a <= i < b for a, b in spans))
        result = []
        for label in dict.fromkeys(labels):
            identifier = self.by_label.get(label)
            if not identifier:
                identifier = str(uuid5(NAMESPACE_URL, "xinshi:survey-language:" + label))
                self.new_languages[label] = identifier
            result.append({"language_id": identifier, "label": label})
        # 返回未完全对应项，绝不把残留内容伪造成词典项。
        return result, [raw] if remainder else []


def education_level(raw):
    lowered = raw.casefold()
    # 在读学历不等于已获得学历，保留原文交由人工确认。
    if any(x in lowered for x in ("在读", "在校", "未毕业", "studying")):
        return None
    for pattern, value in [
        (r"博士|ph\.?d|doctor", "doctor"), (r"硕士|研究生|master|mba", "master"),
        (r"大专|专科|副学士|associate", "associate"),
        (r"本科|学士|bachelor|undergrad|\bba\b|\bbsc\b|一本", "bachelor"),
        (r"中专|中职|职高", "secondary_vocational"),
        (r"高中|初中|小学|high school", "high_school_or_below"),
    ]:
        if re.search(pattern, lowered):
            return value
    return "other" if raw else None


def prepare(rows, catalog, file_hash, sheet):
    resolver = LanguageResolver(catalog)
    records, unresolved = [], []
    for row_no, raw_row in rows:
        values = [clean(x) for x in raw_row]
        name, wechat = values[:2]
        if not name:
            raise ValueError(f"第 {row_no} 行缺少姓名，停止整批计划生成")
        education = education_level(values[8])
        employment = next((v for k, v in [("自由职业", "freelance"), ("在职", "employed"),
                          ("待业", "seeking"), ("在校学生", "student"), ("已退休", "retired")]
                           if k in values[11]), "other" if values[11] else None)
        notes = [f"本地批量导入：{SOURCE}；原表 {sheet} 第 {row_no} 行。"]
        # 联系方式和简历链接只进入各自字段，不复制到不受联系方式权限保护的备注。
        notes.extend(f"原表{COLUMN_NAMES[i]}：{values[i]}" for i in [3,8,9,10,12,13,14,15,16,17] if values[i])
        language_skills, seen = [], set()
        proficiency = next((v for k, v in [("非常熟练", "very_familiar"), ("一般", "familiar"),
                            ("能听，只能讲", "listening_mainly"), ("只会听不会讲", "listening_only")]
                            if k in values[13]), None)
        for column, role, priority in [(12, "dialect_ethnic", 0), (14, "native", 1),
                                      (15, "foreign", 1), (16, "foreign", 2)]:
            languages, pending = resolver.resolve(values[column])
            for item in languages:
                identity = (item["language_id"], role)
                if identity in seen:
                    continue
                seen.add(identity)
                language_skills.append({"language_id": item["language_id"], "role": role,
                    "priority": priority, "proficiency": proficiency if role == "dialect_ethnic" else None,
                    "remarks": f"原表{COLUMN_NAMES[column]}：{values[column]}", "sort_order": len(language_skills)})
            if pending:
                unresolved.append({"row": row_no, "column": column+1, "field": COLUMN_NAMES[column],
                                   "original": values[column], "recognized": [x["label"] for x in languages]})
        certificates = []
        if values[18]:
            for certificate in re.split(r"[\n;；]+", values[18]):
                if not clean(certificate):
                    continue
                other_certificate = re.search(r"驾驶|驾照|营养|会计|计算机|化妆|Makeup|Dubbing", certificate, re.I)
                language_certificate = re.search(r"英语|日语|法语|德语|韩语|朝鲜语|中文|普通话|雅思|托福|CET|TEM|HSK|TOPIK|JLPT|DELE|DALF|CATTI", certificate, re.I)
                certificates.append({"certificate_type": "other" if other_certificate and not language_certificate else "language",
                                     "name": certificate.strip()[:255], "material_received": False,
                                     "remarks": "原表证书及等级：" + values[18],
                                     "sort_order": len(certificates)})
        payload = {
            "full_name": name, "chinese_name": name if re.search(r"[\u3400-\u9fff]", name) else None,
            "english_name": None if re.search(r"[\u3400-\u9fff]", name) else name,
            "wechat": wechat or None, "gender": values[2].split("（")[0].strip() or None,
            "nationality": values[4] or None, "ethnicity": values[5] or None,
            "native_place": values[6] or None, "residence_address": values[7] or None,
            "dialects": [values[12]] if values[12] else [],
            "registration_source": SOURCE, "highest_education": education,
            "employment_status": employment, "employment_detail": values[11] or None,
            "annotation_experience": "\n".join(x for x in [values[19], values[20]] if x) or None,
            "resume_path": values[21] or None, "remarks": "\n".join(notes),
            "status": "standby", "capabilities": [], "annotation_language_skills": [],
            "language_skills": language_skills, "certificates": certificates,
            "education_experiences": [], "allow_duplicate": True,
        }
        if education in {"associate", "bachelor", "master", "doctor"} and (values[9] or values[10]):
            payload["education_experiences"].append({"education_level": education,
                "institution": values[9] or None, "major": values[10] or None,
                "remarks": "原表最高学历：" + values[8], "sort_order": 0})
        records.append({"row": row_no, "idempotency_key": f"survey2609:{file_hash}:{row_no}",
                        "payload": payload, "duplicate_matches": []})
    name_counts = Counter(key(r["payload"]["full_name"]) for r in records)
    wechat_counts = Counter(key(r["payload"]["wechat"] or "") for r in records)
    for record in records:
        payload = record["payload"]
        if name_counts[key(payload["full_name"])] > 1:
            record["duplicate_matches"].append("表内同名")
        if payload["wechat"] and wechat_counts[key(payload["wechat"])] > 1:
            record["duplicate_matches"].append("表内相同微信")
        for person in catalog.get("people", []):
            if key(person["full_name"]) == key(payload["full_name"]):
                record["duplicate_matches"].append("已有同名档案：" + person["id"])
            if payload["wechat"] and key(person.get("wechat") or "") == key(payload["wechat"]):
                record["duplicate_matches"].append("已有相同微信档案：" + person["id"])
    return {"version": 1, "source": SOURCE, "source_sha256": file_hash, "sheet": sheet,
            "policy": "每行独立建档；同名和相同微信全部保留并标记核重；标注语言留空；不覆盖现有档案",
            "new_languages": [{"id": identifier, "label": label} for label, identifier in resolver.new_languages.items()],
            "records": records, "language_review": unresolved,
            "summary": {"records": len(records), "duplicate_review_records": sum(bool(x["duplicate_matches"]) for x in records),
                        "language_skills": sum(len(x["payload"]["language_skills"]) for x in records),
                        "certificates": sum(len(x["payload"]["certificates"]) for x in records),
                        "new_languages": len(resolver.new_languages), "language_review_items": len(unresolved)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import openpyxl
    workbook = openpyxl.load_workbook(args.workbook, read_only=True, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        values = iter(sheet.values)
        headers = next(values)
        if len(headers) != 22 or not all(str(value).startswith(str(i) + "、") for i, value in enumerate(headers, 1)):
            raise ValueError("问卷列顺序或列数发生变化，停止导入准备")
        rows = [(index, row) for index, row in enumerate(values, 2) if any(clean(x) for x in row)]
        plan = prepare(rows, json.loads(args.catalog.read_text(encoding="utf-8")),
                       hashlib.sha256(args.workbook.read_bytes()).hexdigest(), sheet.title)
    finally:
        workbook.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(plan["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
