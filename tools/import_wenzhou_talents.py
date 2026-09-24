"""温州话人才计划的事务导入；默认只读，正式执行要求计划散列与新字段存在。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resource_schemas import ResourcePersonCreate
from sqlalchemy import MetaData, Table, select, text

NESTED = {'allow_duplicate','capabilities','written_profile','interpretation_profile',
          'annotation_profile','annotation_language_skills','career_profile',
          'education_experiences','language_skills','certificates'}

def run(args):
    content = args.plan.read_bytes()
    assert hashlib.sha256(content).hexdigest() == args.sha256, '计划散列不一致'
    plan = json.loads(content)
    assert plan['version']=='wenzhou-talents-v1' and plan['source']=='钟毓整理温州话'
    assert plan['group_mapping']=='same_row' and len(plan['records'])==87
    payloads = [ResourcePersonCreate.model_validate(r['payload']) for r in plan['records']]
    for record,p in zip(plan['records'],payloads):
        assert record['idempotency_key']==f"wenzhou20260924:{plan['source_sha256']}:{record['row']}"
        assert p.full_name==record['original_values'][4] and p.wechat_groups==record['original_values'][0]
        assert p.registration_source==plan['source'] and not p.annotation_language_skills
        assert len(p.capabilities)==1 and p.capabilities[0].capability_type=='annotation'
        assert len(p.language_skills)==1 and p.language_skills[0].role=='native'
    assert len({r['idempotency_key'] for r in plan['records']})==87
    # 显式指定已核对的运行目录；不复制环境凭据到隔离工作区。
    sys.path.insert(0,str(args.runtime_root))
    from database import engine
    assert engine.url.host=='43.132.156.72' and engine.url.database=='xinshi_system'
    with engine.connect() as conn:
        conn.execute(text('SET TRANSACTION READ ONLY'))
        language=conn.execute(text('SELECT id FROM interpretation_language WHERE label=:label'),{'label':'温州话'}).scalar_one()
        assert all(p.language_skills[0].language_id==language for p in payloads)
        has_field=bool(conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='resource_person' AND column_name='wechat_groups'")).first())
    print(json.dumps({'validated':87,'wechat_groups_exists':has_field,'apply':args.apply}))
    if not args.apply:
        return
    assert has_field, '必须先完成新字段迁移'
    assert args.output and not args.output.exists(), '备份目录必须为新的目录'
    args.output.mkdir(parents=True)
    meta=MetaData()
    tables={name:Table(name,meta,autoload_with=engine,resolve_fks=False) for name in
            ['resource_person','resource_language_skill','resource_capability','resource_annotation_language_skill']}
    people, languages, capabilities, annotations=(tables[n] for n in tables)
    expected=[]
    report={'source':plan['source'],'created':[],'skipped':[]}
    def verify(conn):
        for identifier,p in expected:
            row=dict(conn.execute(select(people).where(people.c.id==identifier)).mappings().one())
            for key,value in p.model_dump(exclude=NESTED).items():
                if key=='resource_code' and value is None:
                    assert row[key]
                else:
                    assert row[key]==value, f'字段核验失败：{key}'
            for table,wanted in [(languages,[s.model_dump(exclude={'id'}) for s in p.language_skills]),
                                 (capabilities,[s.model_dump() for s in p.capabilities])]:
                actual=list(conn.execute(select(table).where(table.c.person_id==identifier)).mappings())
                assert len(actual)==len(wanted)==1
                assert all(actual[0][k]==v for k,v in wanted[0].items())
            assert not conn.execute(select(annotations.c.id).where(annotations.c.person_id==identifier)).first()
    with engine.begin() as conn:
        conn.execute(text('SELECT pg_advisory_xact_lock(2609,87)'))
        conn.execute(text('LOCK TABLE resource_person IN SHARE ROW EXCLUSIVE MODE'))
        before=[dict(r) for r in conn.execute(select(people)).mappings()]
        (args.output/'before.json').write_text(json.dumps(before,ensure_ascii=False,default=str),encoding='utf-8')
        by_key={r['idempotency_key']:r for r in before if r['idempotency_key']}
        names={str(r['full_name']).strip().casefold() for r in before}
        for record,p in zip(plan['records'],payloads):
            prior=by_key.get(record['idempotency_key'])
            if prior:
                assert prior['registration_source']==plan['source']
                identifier=prior['id']
                report['skipped'].append({'row':record['row'],'id':str(identifier)})
            else:
                identifier=uuid.uuid4()
                conn.execute(people.insert().values(id=identifier,idempotency_key=record['idempotency_key'],
                    duplicate_review_required=p.full_name.strip().casefold() in names,**p.model_dump(exclude=NESTED)))
                for skill in p.language_skills:
                    conn.execute(languages.insert().values(id=uuid.uuid4(),person_id=identifier,**skill.model_dump(exclude={'id'})))
                for capability in p.capabilities:
                    conn.execute(capabilities.insert().values(id=uuid.uuid4(),person_id=identifier,source='batch_import',**capability.model_dump()))
                report['created'].append({'row':record['row'],'id':str(identifier)})
            expected.append((identifier,p))
        verify(conn)
        current={r['id']:dict(r) for r in conn.execute(select(people)).mappings()}
        changes=[{k for k,v in r.items() if current[r['id']][k]!=v} for r in before]
        assert all(not fields-{'name_duplicate'} for fields in changes), '原有业务资料发生变化'
        report['existing_duplicate_flags_refreshed']=sum(bool(f) for f in changes)
    with engine.connect() as conn:
        verify(conn)
    report.update(verified=87,native_language='温州话',capability='annotation',annotation_languages=0,
                  discarded_trailing_groups=34,existing_business_records_changed=0)
    (args.output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:len(v) if isinstance(v,list) else v for k,v in report.items()},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--runtime-root',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',type=Path)
    run(parser.parse_args())
