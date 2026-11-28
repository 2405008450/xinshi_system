"""统计报表按已保存财务金额批量取数，保留缺价信息，不混合币种。"""
from uuid import UUID
from sqlalchemy import inspect

def attach_finance(db,module,selected):
 if not selected:return
 ids=[UUID(str(item['id'])) for item in selected]
 if module=='translation':
  from models import TranslationProject as Project,TranslationSubOrder as Child
  from sqlalchemy.orm import joinedload,selectinload
  from translation_customer_finance import tree
  from translation_document_requirements import load_order_pricing_modes
  import sub_client_finance
  import crud
  projects=db.query(Project).options(joinedload(Project.client),joinedload(Project.sub_client),selectinload(Project.customer_charge_items),selectinload(Project.sub_orders).selectinload(Child.customer_charge_items)).filter(Project.id.in_(ids)).all()
  # tree() also reads saved pricing modes and child-client preferences. Prime
  # their request-local caches once instead of issuing one query per project.
  load_order_pricing_modes(db,projects)
  sub_client_finance.load(db,{project.sub_client_id for project in projects if project.sub_client_id})
  crud._attach_word_count_matrices(db,projects=projects)
  metadata={str(item['id']):item for item in selected}
  for project in projects:
   project.client_name=metadata[str(project.id)]['client_name'];project.client_short_name=metadata[str(project.id)]['client_short_name']
  values={str(project.id):tree(project,summary_only=True,include_billing_tax_mode=False)['item'] for project in projects}
  for item in selected:item['finance']=values.get(str(item['id']),{})
  return
 if module=='interpretation':
  from interpretation_customer_finance import InterpretationCustomerFinance,calculate,incomplete_tax_basis
  if not inspect(db.connection()).has_table(InterpretationCustomerFinance.__tablename__):return
  payloads={str(row.project_id):row.payload for row in db.query(InterpretationCustomerFinance).filter(InterpretationCustomerFinance.project_id.in_(ids))}
  for item in selected:
   payload=payloads.get(str(item['id']))
   if payload:
    item['finance']=calculate(payload)
    item['incomplete_excl_tax']=incomplete_tax_basis(payload,'excl_tax');item['incomplete_incl_tax']=incomplete_tax_basis(payload,'incl_tax')
  return
 import business_finance as finance
 from project_customer_finance import ProjectCustomerFinanceHistory,MODELS
 model=MODELS[module]
 projects=db.query(model).filter(model.id.in_(ids)).all()
 if not inspect(db.connection()).has_table(ProjectCustomerFinanceHistory.__tablename__):return
 values=finance.records(db,module,projects)
 for item in selected:
  project=next((project for project in projects if str(project.id)==str(item['id'])),None)
  if project:
   payload=finance.normalized(module,project,values[project.id].payload)
   item['finance']=finance.totals(payload)

def attach_order_details(result,selected,bounds,basis):
 groups={}
 for item in selected:
  key=(bounds(item['day'])[0].isoformat(),item['client_key'])
  amounts=item['finance'].get('totals_'+basis,{})
  groups.setdefault(key,[]).append(dict(id=str(item['id']),client_id=item['client_key'],client_name=item['client_name'],client_short_name=item['client_short_name'],cohort=item.get('cohort'),order_no=item['order_no'],project_name=item['project_name'],order_date=item['day'].isoformat(),status=item.get('status',''),amounts=amounts,amount_complete=bool(amounts) and not item.get('incomplete',False)))
 for row in result['customers']:row['orders']=groups.get((row['period_start'],row['client_id']),[])
 for row in result['periods']:row['orders']=[order for (period,_),orders in groups.items() if period==row['period_start'] for order in orders]
