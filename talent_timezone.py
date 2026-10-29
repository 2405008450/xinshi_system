"""人才所在地固定 UTC 偏移，仅作为资料字段，不改变系统业务时间。"""
import re


def normalize_talent_timezone(value):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    match = re.fullmatch(r'UTC([+-])(\d{1,2})(?::(00|15|30|45))?', str(value).strip())
    if not match:
        raise ValueError('时区请使用 UTC+8 或 UTC+5:30 等格式')
    sign, hour, minute = match.groups()
    hour, minute = int(hour), int(minute or 0)
    total = (hour * 60 + minute) * (-1 if sign == '-' else 1)
    if not -720 <= total <= 840:
        raise ValueError('时区必须介于 UTC-12 与 UTC+14 之间')
    if total == 0:
        return 'UTC+0'
    return f"UTC{sign}{hour}" + (f':{minute:02d}' if minute else '')
