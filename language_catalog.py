"""翻译项目使用的受控语种库。

语种使用稳定代码区分地区或书写体系，项目当前仍保存中文展示名称组成的语言对，
以兼容稿件安排、邮件模板和既有报表。
"""

import re
from typing import Optional


LANGUAGE_VARIANTS = (
    {"code": "zh-CN", "label": "中文（简体）", "aliases": ["中文", "简中", "简体中文", "大陆中文"]},
    {"code": "zh-TW", "label": "中文（繁体·台湾）", "aliases": ["繁中", "繁体中文", "台湾中文"]},
    {"code": "zh-HK", "label": "中文（繁体·香港）", "aliases": ["香港中文", "港式中文", "繁体香港"]},
    {"code": "en-US", "label": "英语（美国）", "aliases": ["英文", "英语", "美式英语", "美式英文"]},
    {"code": "en-GB", "label": "英语（英国）", "aliases": ["英式英语", "英式英文", "英国英语"]},
    {"code": "es-419", "label": "西班牙语（拉丁美洲）", "aliases": ["西语", "拉美西语", "拉丁美洲西语"]},
    {"code": "es-ES", "label": "西班牙语（欧洲）", "aliases": ["西语", "欧洲西语", "西班牙西语"]},
    {"code": "pt-BR", "label": "葡萄牙语（巴西）", "aliases": ["葡语", "巴西葡语"]},
    {"code": "pt-PT", "label": "葡萄牙语（葡萄牙）", "aliases": ["葡语", "欧洲葡语"]},
    {"code": "fr-FR", "label": "法语（法国）", "aliases": ["法文", "法语", "法国法语"]},
    {"code": "fr-CA", "label": "法语（加拿大）", "aliases": ["加拿大法语", "魁北克法语"]},
    {"code": "de-DE", "label": "德语（德国）", "aliases": ["德文", "德语"]},
    {"code": "it-IT", "label": "意大利语", "aliases": ["意大利文"]},
    {"code": "nl-NL", "label": "荷兰语", "aliases": ["荷兰文"]},
    {"code": "ru-RU", "label": "俄语", "aliases": ["俄文"]},
    {"code": "uk-UA", "label": "乌克兰语", "aliases": ["乌克兰文"]},
    {"code": "pl-PL", "label": "波兰语", "aliases": ["波兰文"]},
    {"code": "cs-CZ", "label": "捷克语", "aliases": ["捷克文"]},
    {"code": "sk-SK", "label": "斯洛伐克语", "aliases": ["斯洛伐克文"]},
    {"code": "hu-HU", "label": "匈牙利语", "aliases": ["匈牙利文"]},
    {"code": "ro-RO", "label": "罗马尼亚语", "aliases": ["罗马尼亚文"]},
    {"code": "bg-BG", "label": "保加利亚语", "aliases": ["保加利亚文"]},
    {"code": "sr-Latn", "label": "塞尔维亚语（拉丁字母）", "aliases": ["塞尔维亚语拉丁"]},
    {"code": "sr-Cyrl", "label": "塞尔维亚语（西里尔字母）", "aliases": ["塞尔维亚语西里尔"]},
    {"code": "el-GR", "label": "希腊语", "aliases": ["希腊文"]},
    {"code": "tr-TR", "label": "土耳其语", "aliases": ["土耳其文"]},
    {"code": "sv-SE", "label": "瑞典语", "aliases": ["瑞典文"]},
    {"code": "da-DK", "label": "丹麦语", "aliases": ["丹麦文"]},
    {"code": "nb-NO", "label": "挪威语（博克马尔）", "aliases": ["挪威语", "书面挪威语"]},
    {"code": "fi-FI", "label": "芬兰语", "aliases": ["芬兰文"]},
    {"code": "is-IS", "label": "冰岛语", "aliases": ["冰岛文"]},
    {"code": "ja-JP", "label": "日语", "aliases": ["日文"]},
    {"code": "ko-KR", "label": "韩语", "aliases": ["韩文", "韩国语"]},
    {"code": "vi-VN", "label": "越南语", "aliases": ["越南文"]},
    {"code": "th-TH", "label": "泰语", "aliases": ["泰文"]},
    {"code": "id-ID", "label": "印度尼西亚语", "aliases": ["印尼语", "印度尼西亚文"]},
    {"code": "ms-MY", "label": "马来语", "aliases": ["马来文", "马来西亚语"]},
    {"code": "hi-IN", "label": "印地语", "aliases": ["印地文"]},
    {"code": "bn-BD", "label": "孟加拉语", "aliases": ["孟加拉文"]},
    {"code": "ar-MSA", "label": "阿拉伯语（现代标准）", "aliases": ["阿语", "阿拉伯文", "现代标准阿语"]},
    {"code": "he-IL", "label": "希伯来语", "aliases": ["希伯来文"]},
    {"code": "fa-IR", "label": "波斯语", "aliases": ["波斯文"]},
    {"code": "ur-PK", "label": "乌尔都语", "aliases": ["乌尔都文"]},
    {"code": "kk-KZ", "label": "哈萨克语", "aliases": ["哈萨克文"]},
    {"code": "mn-MN", "label": "蒙古语（西里尔字母）", "aliases": ["蒙古语", "蒙古文"]},
    {"code": "bo-CN", "label": "藏语", "aliases": ["藏文"]},
    {"code": "my-MM", "label": "缅甸语", "aliases": ["缅甸文"]},
    {"code": "km-KH", "label": "高棉语", "aliases": ["柬埔寨语", "高棉文"]},
    {"code": "lo-LA", "label": "老挝语", "aliases": ["老挝文"]},
)

# 用于“中英、英中、中译英、拉美西”等业务习惯简称的搜索映射。
# 同一基础语种的地区变体共享通用简称，搜索后再由用户选择具体地区。
LANGUAGE_SEARCH_SHORTCUTS = {
    "zh-CN": ["中", "中文", "简中"],
    "zh-TW": ["中", "中文", "繁中", "台繁"],
    "zh-HK": ["中", "中文", "繁中", "港繁"],
    "en-US": ["英", "英文", "英语", "美英"],
    "en-GB": ["英", "英文", "英语", "英英"],
    "es-419": ["西", "西语", "拉美西", "拉美西语"],
    "es-ES": ["西", "西语", "欧西", "欧洲西语"],
    "pt-BR": ["葡", "葡语", "巴葡"],
    "pt-PT": ["葡", "葡语", "欧葡"],
    "fr-FR": ["法", "法文", "法语", "法国法语"],
    "fr-CA": ["法", "法文", "法语", "加法"],
    "de-DE": ["德", "德文", "德语"],
    "it-IT": ["意", "意文", "意大利语"],
    "nl-NL": ["荷", "荷文", "荷兰语"],
    "ru-RU": ["俄", "俄文", "俄语"],
    "uk-UA": ["乌克兰", "乌克兰语"],
    "pl-PL": ["波兰", "波兰语"],
    "cs-CZ": ["捷克", "捷克语"],
    "sk-SK": ["斯洛伐克", "斯洛伐克语"],
    "hu-HU": ["匈", "匈牙利语"],
    "ro-RO": ["罗", "罗马尼亚语"],
    "bg-BG": ["保", "保加利亚语"],
    "sr-Latn": ["塞", "塞语", "塞尔维亚语"],
    "sr-Cyrl": ["塞", "塞语", "塞尔维亚语"],
    "el-GR": ["希腊", "希腊语"],
    "tr-TR": ["土", "土语", "土耳其语"],
    "sv-SE": ["瑞", "瑞典语"],
    "da-DK": ["丹", "丹麦语"],
    "nb-NO": ["挪", "挪威语"],
    "fi-FI": ["芬", "芬兰语"],
    "is-IS": ["冰", "冰岛语"],
    "ja-JP": ["日", "日文", "日语"],
    "ko-KR": ["韩", "韩文", "韩语"],
    "vi-VN": ["越", "越南语"],
    "th-TH": ["泰", "泰文", "泰语"],
    "id-ID": ["印尼", "印尼语"],
    "ms-MY": ["马来", "马来语"],
    "hi-IN": ["印地", "印地语"],
    "bn-BD": ["孟加拉", "孟加拉语"],
    "ar-MSA": ["阿", "阿文", "阿语"],
    "he-IL": ["希伯来", "希伯来语"],
    "fa-IR": ["波斯", "波斯语"],
    "ur-PK": ["乌尔都", "乌尔都语"],
    "kk-KZ": ["哈", "哈萨克语"],
    "mn-MN": ["蒙", "蒙古语"],
    "bo-CN": ["藏", "藏文", "藏语"],
    "my-MM": ["缅", "缅甸语"],
    "km-KH": ["柬", "高棉", "柬埔寨语"],
    "lo-LA": ["老", "老挝语"],
}

LANGUAGE_PAIR_SPLIT_PATTERN = re.compile(r"[；;，,、\n]+")
LANGUAGE_LABEL_FORBIDDEN_PATTERN = re.compile(r"[→；;,，、\r\n]")


def compact_language_name(value: object) -> str:
    """返回项目名称使用的业务语种简称，例如“法语（法国）”返回“法”。"""
    normalized = " ".join(str(value or "").split())
    normalized_key = normalized.casefold()
    for item in LANGUAGE_VARIANTS:
        candidates = [item["label"], *item.get("aliases", [])]
        if any(candidate.casefold() == normalized_key for candidate in candidates):
            shortcuts = LANGUAGE_SEARCH_SHORTCUTS.get(item["code"], [])
            return shortcuts[0] if shortcuts else normalized
    return re.sub(r"[（(].*?[）)]", "", normalized).removesuffix("语").removesuffix("文")


def compact_translation_direction(value: object) -> str:
    """将规范语言对转换为项目名称用简称，例如“法语（法国）→中文（简体）”转为“法译中”。"""
    directions = []
    for item in LANGUAGE_PAIR_SPLIT_PATTERN.split(str(value or "")):
        item = item.strip()
        if not item:
            continue
        source, separator, target = item.partition("→")
        if not separator:
            directions.append(item)
            continue
        directions.append(f"{compact_language_name(source)}译{compact_language_name(target)}")
    return "、".join(directions)


def get_searchable_language_variants() -> list[dict]:
    """返回带业务简称映射的前端候选语种。"""
    return [
        {
            **item,
            "shortcuts": LANGUAGE_SEARCH_SHORTCUTS.get(item["code"], []),
        }
        for item in LANGUAGE_VARIANTS
    ]


def normalize_language_label(value: object) -> str:
    """规范语种名称，并阻止名称占用翻译方向的结构分隔符。"""
    normalized = " ".join(str(value or "").split())
    if not normalized:
        raise ValueError("语种名称不能为空")
    if len(normalized) > 100:
        raise ValueError("语种名称不能超过100个字符")
    if LANGUAGE_LABEL_FORBIDDEN_PATTERN.search(normalized):
        raise ValueError("语种名称不能包含箭头或列表分隔符")
    return normalized


def normalize_language_pairs(value: Optional[str]) -> Optional[str]:
    """校验语言对结构并规范化；目录成员校验由持有数据库会话的业务层完成。"""
    if value is None:
        return None

    parts = [
        item.strip()
        for item in LANGUAGE_PAIR_SPLIT_PATTERN.split(str(value))
        if item.strip()
    ]
    if not parts:
        return None

    normalized = []
    normalized_keys = set()
    for pair in parts:
        source, separator, target = pair.partition("→")
        if separator != "→":
            raise ValueError(f"“{pair}”不是有效的翻译方向，请使用“原文语种→译文语种”格式")
        source = normalize_language_label(source)
        target = normalize_language_label(target)
        if source.casefold() == target.casefold():
            raise ValueError("翻译方向的原文语种和译文语种不能相同")
        canonical_pair = f"{source}→{target}"
        canonical_key = canonical_pair.casefold()
        if canonical_key not in normalized_keys:
            normalized.append(canonical_pair)
            normalized_keys.add(canonical_key)
    return "；".join(normalized)


def validate_language_pairs_against_catalog(
    value: Optional[str], available_labels: list[str] | tuple[str, ...] | set[str],
) -> Optional[str]:
    """确认语言对两端均存在于共享目录，并返回使用目录规范名称的结果。"""
    normalized = normalize_language_pairs(value)
    if normalized is None:
        return None

    catalog = {
        normalize_language_label(label).casefold(): normalize_language_label(label)
        for label in available_labels
    }
    result = []
    result_keys = set()
    for pair in LANGUAGE_PAIR_SPLIT_PATTERN.split(normalized):
        source, _, target = pair.partition("→")
        source_label = catalog.get(source.casefold())
        target_label = catalog.get(target.casefold())
        missing = [label for label, canonical in ((source, source_label), (target, target_label)) if canonical is None]
        if missing:
            raise ValueError(f"语种“{'、'.join(missing)}”不在共享语种目录中")
        canonical_pair = f"{source_label}→{target_label}"
        canonical_key = canonical_pair.casefold()
        if canonical_key not in result_keys:
            result.append(canonical_pair)
            result_keys.add(canonical_key)
    return "；".join(result)
