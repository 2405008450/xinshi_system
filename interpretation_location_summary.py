"""对外项目名称与需求发布只使用城市，完整地点仍保存在项目明细。"""
import re


def interpretation_cities(payload):
    cities=[]
    legacy=[]
    for period in payload.time_ranges:
        details=period.location_details
        if details is not None:
            cities.extend(location.city.strip() for location in details if location.city.strip())
        else:
            legacy.extend(period.locations or [])
    if not payload.time_ranges or all(period.location_details is None and not period.locations for period in payload.time_ranges):
        legacy.extend(payload.locations)
    # 老数据可能只保存城市，或用空格连接省/城市/地址；不把详细地址直接带到对外文案。
    for value in legacy:
        value=str(value or '').strip()
        parts=re.split(r'\s+',value)
        city=next((part for part in parts if part.endswith('市')),None)
        if city:
            city=re.sub(r'^中国','',city)
            city=re.split(r'省|自治区|特别行政区',city)[-1]
        if not city and len(parts)==1 and not re.search(r'[省区县路街道号楼村镇]|中国|国家',value):
            city=value
        if city:cities.append(city)
    return list(dict.fromkeys(cities))
