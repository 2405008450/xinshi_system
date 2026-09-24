"""按姓名列和同行微信群准备温州话人才计划；不访问数据库。"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resource_schemas import ResourcePersonCreate

SOURCE = '钟毓整理温州话'
LANGUAGE_ID = 'eba52093-9aa7-4f59-9313-b1b48bd62c32'

def merge_native_place(city, district):
    city, district = str(city or '').strip(), str(district or '').strip()
    if not city:
        return district or None
    if not district or district in city:
        return city
    if district.startswith(city):
        return district
    return f'{city} / {district}'

def prepare(source):
    records = []
    for original in source['records']:
        row, values = original['excel_row'], original['values']
        group, _, _, _, name, gender, age, city, district, residence, education, employment, school, performance = values
        if not name:
            continue
        notes = [f'原表：{SOURCE}，Sheet1第{row}行', '微信群按原表同一行对应，姓名以姓名列为准。']
        for label, value in [('原表年龄', age), ('户籍市', city), ('户籍区/县', district), ('最后学历', education), ('身份', employment), ('简历（学校）', school)]:
            if value is not None:
                notes.append(f'{label}：{value}')
        job = str(employment or '')
        state = None
        if '学生' in job or job in {'大一', '大二', '大三', '大四'}:
            state = 'student'
        elif '自由职业' in job:
            state = 'freelance'
        elif '退休' in job:
            state = 'retired'
        elif job:
            state = 'employed'
        level = None
        if performance:
            if any(x in performance for x in ['配合度高', '配合度较高', '配合度比较高', '配合度极高']):
                level = 'high'
            elif any(x in performance for x in ['配合度中', '配合度一般']):
                level = 'medium'
            elif '配合度低' in performance:
                level = 'low'
        payload = ResourcePersonCreate(
            full_name=name, wechat_groups=group, registration_source=SOURCE, gender=gender,
            reported_age=age,
            ancestral_home=merge_native_place(city, district),
            residence_address=residence, employment_status=state, employment_detail=employment,
            highest_education={'本科':'bachelor', '大专':'associate'}.get(education),
            overall_rating=performance, cooperation_level=level,
            cooperation_note=performance if level else None,
            punctuality_level='high' if performance and '守时度高' in performance else None,
            punctuality_note=performance if performance and '守时度高' in performance else None,
            remarks='\n'.join(notes), status='standby', allow_duplicate=True,
            capabilities=[{'capability_type':'annotation', 'status':'active'}],
            language_skills=[{'language_id':LANGUAGE_ID, 'role':'native', 'priority':1, 'sort_order':0}],
        )
        assert payload.birth_date is None and payload.birth_year_month is None
        assert payload.native_place is None
        assert not payload.annotation_language_skills
        records.append({'row':row,'idempotency_key':f"wenzhou20260924:{source['source_sha256']}:{row}",
                        'payload':payload.model_dump(mode='json'),'original_values':values})
    assert len(records) == 87 and len({r['row'] for r in records}) == 87
    return {'version':'wenzhou-talents-v1','source':SOURCE,'source_sha256':source['source_sha256'],
            'group_mapping':'same_row','discarded_trailing_group_count':34,'records':records}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    plan = prepare(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'validated':len(plan['records']),'group_mapping':plan['group_mapping'],
                      'discarded_groups':34,'capability':'annotation','native_language':'温州话'},ensure_ascii=False))
