"""局域网资源开拓历史导入；默认完整试运行回滚，--apply 才提交。"""
import argparse,json,socket,sys,hashlib
from pathlib import Path
from uuid import UUID,uuid4,uuid5,NAMESPACE_URL
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--apply',action='store_true');p.add_argument('--migrate',action='store_true');p.add_argument('--output',required=True);args=p.parse_args()
 assert socket.gethostname().upper()=='WIN-LOLJ8UHT2G5' and ROOT==Path(r'E:\xinshi_system'), '仅允许局域网调试机'
 import main as app_models
 from database import engine,SessionLocal
 from sqlalchemy import text
 from models import AppUser
 from interpretation_models import InterpretationLanguage
 from resource_models import ResourcePerson
 from resource_development_models import DevelopmentRecord as Record,DevelopmentOption as Option,DevelopmentCounter as Counter,DevelopmentAction as Action,DevelopmentLanguage as Language,DevelopmentAudit as Audit
 from resource_development_schemas import RecordWrite
 from resource_development_service import save_record,lock_writes,audit,refresh_draft,can_delegate,snapshot
 if args.migrate:
  sql=(ROOT/'data/migrations/20260924_resource_development_history.sql').read_text(encoding='utf-8').replace('BEGIN;','').replace('COMMIT;','')
  with engine.begin() as conn:conn.execute(text(sql))
 data=json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
 assert data['policy']['destination']=='resource_development_only' and not data['policy']['create_talent'] and not data['policy']['link_talent']
 assert len(data['records'])==938 and data['source']['sha256']=='11b323edfe1753917ab42a7b769e1a096484b79f85e3394518854004335b92d8'
 report={'apply':args.apply,'source_sha256':data['source']['sha256'],'created':[],'skipped':[],'options_created':[],'languages_created':[],'preserved_unmapped':[]}
 with SessionLocal() as db:
  lock_writes(db)
  actor=db.query(AppUser).filter_by(username='jinghan',is_active=True).one()
  assert can_delegate(db,actor)
  before=db.query(ResourcePerson).count()
  opts={(x.kind,x.name):x for x in db.query(Option).all()};langs={x.label:x for x in db.query(InterpretationLanguage).all()}; touched=set(); pending=[]; children=[]; existing={x.id:x for x in db.query(Record).all()}; counters={(x.platform_id,x.work_date):x for x in db.query(Counter).all()}; active_users={x.id for x in db.query(AppUser).filter_by(is_active=True)}
  def opt(kind,name):
   key=(kind,name)
   if key in opts:return opts[key]
   row=Option(id=uuid4(),kind=kind,name=name,category=('international' if name in ['Facebook','领英','HiredChina'] else 'local' if '招聘网' in name else 'national') if kind=='platform' else '',code=('IMP'+hashlib.sha256(name.encode()).hexdigest()[:12].upper()) if kind=='platform' else None,description='资源开拓统筹历史导入配置；原表写法保留于记录备注',revision=1)
   db.add(row);audit(db,actor,row,'create');opts[key]=row;report['options_created'].append(name);return row
  for r in data['records']:
   rid=UUID(r['staging_id']);old=existing.get(rid)
   if old:
    assert old.historical_only and old.person_id is None
    report['skipped'].append({'row':r['source_row'],'id':str(old.id),'reason':'本批已导入'});continue
   if r['existing_record_id']:
    old=existing.get(UUID(r['existing_record_id']))
    assert old and str(old.owner_id)==r['owner_id'] and old.full_name==r['full_name'] and old.work_date.isoformat()==r['work_date'] and old.phone==r['phone'] and old.wechat==r['wechat'] and str(old.platform_id)==r['platform_id'], '已有样例已变化，请核实'
    report['skipped'].append({'row':r['source_row'],'id':str(old.id),'reason':'已有测试样例'});continue
   platform=opt('platform',r['platform_name'] or '来源待确认')
   account=None if '待发' in r['account_name'] else opt('account',r['account_name']) if r['account_name'] else None
   language_ids=[];unmapped=[]
   for l in r['languages']:
    name=l['label'];lang=langs.get(name)
    if not lang and any(x in name for x in ['话','方言','粤语','客家','吴语','闽南','晋语','赣南语']) and not any(x in name for x in ['团队','标注']):
     lang=InterpretationLanguage(id=uuid4(),label=name,language_type='dialect',is_active=True,is_custom=True,created_by=actor.id,updated_by=actor.id);db.add(lang);db.flush();langs[name]=lang;report['languages_created'].append(name)
    if lang and lang.is_active:language_ids.append(lang.id)
    else:unmapped.append(l['raw'])
   markers={a['channel']:{'status':a['status'],'action_date':a['action_date'],'operator_name':a['operator_name'],'raw':a['raw']} for a in r['actions']}
   actions=[dict(id=uuid5(rid,a['channel']),channel=a['channel'],status=a['status'],action_date=a['action_date'],operator_id=a['operator_id'],account_id=None) for a in r['actions'] if a['action_date'] and a['operator_id']]
   notes=[r['remarks_raw'],f"【历史导入】资源开拓统筹.xlsx / Sheet1 第{r['source_row']}行；仅保留开拓标记，不关联人才。",'【原表信息】'+json.dumps(dict(zip(data['source']['headers'],r['raw_values'])),ensure_ascii=False),'【待核对】'+'；'.join(r['review_reasons']) if r['review_reasons'] else '','【未映射语种原文】'+'、'.join(unmapped) if unmapped else '']
   payload=RecordWrite(id=rid,platform_id=platform.id,work_date=r['work_date'],owner_id=r['owner_id'],full_name=r['full_name'],account_id=account.id if account else None,phone=r['phone'],wechat=r['wechat'],language_ids=list(dict.fromkeys(language_ids)),remarks='\n'.join(x for x in notes if x),actions=actions)
   assert payload.owner_id in active_users and all(a.operator_id in active_users for a in payload.actions)
   key=(platform.id,payload.work_date);counter=counters.get(key)
   if not counter:
    counter=Counter(platform_id=platform.id,work_date=payload.work_date,value=0);db.add(counter);counters[key]=counter
   counter.value+=1
   row=Record(
    id=rid,platform_id=platform.id,work_date=payload.work_date,owner_id=payload.owner_id,full_name=payload.full_name,account_id=payload.account_id,phone=payload.phone,wechat=payload.wechat,follow_up='',remarks=payload.remarks,duplicate_note='',
    greeting_no=f'{platform.code}-{payload.work_date:%y%m%d}-{counter.value:03d}',historical_only=True,historical_markers=markers,wechat_status=r['wechat_status'],enterprise_status=r['enterprise_status'],person_id=None,revision=1,created_by=actor.id,updated_by=actor.id)
   db.add(row);pending.append(row)
   children.extend([Language(record_id=rid,language_id=x) for x in payload.language_ids])
   for a in payload.actions:
    entry=Action(**a.model_dump(),record_id=rid,request_number=0,created_by=actor.id,updated_by=actor.id);children.append(entry);pending.append(entry)
   assert row.person_id is None and row.historical_only
   touched.add((row.owner_id,row.work_date));report['created'].append({'row':r['source_row'],'id':str(row.id),'greeting_no':row.greeting_no})
   if unmapped or r['review_reasons']:report['preserved_unmapped'].append(r['source_row'])
  db.flush()
  db.add_all(children);db.flush()
  db.add_all([Audit(entity_id=x.id,entity_type=x.__tablename__.removeprefix('resource_development_'),actor_id=actor.id,action='create',before={},after=snapshot(x)) for x in pending])
  for owner,day in touched:refresh_draft(db,owner,day)
  db.flush();after=db.query(ResourcePerson).count();assert before==after
  report.update(talent_before=before,talent_after=after,created_count=len(report['created']),skipped_count=len(report['skipped']),checked_at=datetime.now().isoformat())
  assert report['created_count']+report['skipped_count']==938
  # 提交前完整核对关联明细，避免主记录成功但历史/语种遗漏。
  stored_actions={x.id for x in db.query(Action).all()}
  stored_links={(x.record_id,x.language_id) for x in db.query(Language).all()}
  for item in data['records']:
   if item['existing_record_id']:continue
   rid=UUID(item['staging_id'])
   for entry in item['actions']:
    if entry['action_date'] and entry['operator_id']:assert uuid5(rid,entry['channel']) in stored_actions
   for entry in item['languages']:
    lang=langs.get(entry['label'])
    if lang and lang.is_active:assert (rid,lang.id) in stored_links
  if args.apply:db.commit()
  else:db.rollback()
 Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if not isinstance(v,list)},ensure_ascii=False))
if __name__=='__main__':main()



