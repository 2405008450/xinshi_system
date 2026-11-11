"""开票资料、主体目录和客户项目记录隔离测试。"""
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
from tools.apply_invoice_parties_migration import apply_migration
import invoice_parties as parties
import translation_customer_finance as finance
import translation_project_invoices as invoices


def setup(context):
    http,db,clients,permissions,actor=context
    apply_migration(db.connection());db.commit()
    http.app.include_router(parties.router);http.app.include_router(finance.router)
    return http,db,clients,permissions,actor


def test_three_subjects_blank_and_migration_repeat_preserves_filled_data(context):
    http,db,_,permissions,_=setup(context)
    values=http.get('/invoice-parties/subjects').json()['items']
    assert [item['name'] for item in values]==['广州信实翻译服务有限公司','广州信实翻译服务有限公司深圳分公司','广州信实翻译服务有限公司上海分公司']
    assert all(not item['complete'] and not item['party']['tax_number'] for item in values)
    permissions.add('system:organization:write')
    data={**values[0]['party'],'tax_number':'TEST-GZ','bank':'测试银行'}
    saved=http.put('/invoice-parties/subjects/guangzhou',json={'revision':1,'party':data})
    assert saved.status_code==200,saved.text
    assert saved.json()['updated_at'].endswith('+08:00')
    apply_migration(db.connection());db.commit();db.expire_all()
    assert parties.subject(db,'guangzhou')['party']['tax_number']=='TEST-GZ'
    assert http.put('/invoice-parties/subjects/guangzhou',json={'revision':1,'party':data}).status_code==409


def test_client_profile_subject_live_join_and_permissions(context):
    http,db,clients,permissions,_=setup(context)
    path=f'/invoice-parties/clients/{clients[0].id}'
    assert http.get(path).json()['revision']==0
    saved=http.put(path,json={'revision':0,'party':{'title':'测试开票抬头','tax_number':'TEST-TAX','address':'测试注册地址','bank_account':'TEST-ACCOUNT'},'subject_key':'shenzhen','invoice_kind':'special'})
    assert saved.status_code==200,saved.text
    assert saved.json()['subject']['name']=='广州信实翻译服务有限公司深圳分公司'
    assert http.put(path,json={'revision':0,'party':{'title':'过期修改'}}).status_code==409
    permissions.add('system:organization:write')
    http.put('/invoice-parties/subjects/shenzhen',json={'revision':1,'party':{'tax_number':'TEST-SZ','bank':'主体新银行'}})
    assert http.get(path).json()['subject']['party']['bank']=='主体新银行'
    permissions.remove('clients:write');permissions.remove('system:organization:write')
    assert http.put(path,json={'revision':1,'party':{'title':'无权修改'}}).status_code==403
    assert http.put('/invoice-parties/subjects/shenzhen',json={'revision':2,'party':{}}).status_code==403
    assert http.get(path).json()['party']['title']=='测试开票抬头'


def test_customer_project_records_scope_filters_summary_pagination(context):
    http,db,clients,permissions,actor=setup(context);permissions.add('projects:write')
    first=project(db,clients[0],'INV-PROFILE-A',fixed=True)
    second=project(db,clients[0],'INV-PROFILE-B',fixed=True)
    pending=project(db,clients[0],'INV-PROFILE-C',fixed=True)
    no_need=project(db,clients[0],'INV-PROFILE-D',fixed=True)
    other=project(db,clients[1],'INV-PROFILE-OTHER',fixed=True)
    for row in (first,second,pending,other):
        current=finance.read(db,row.id)
        finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=500,adjusted_total_incl_tax=530,billing_tax_mode='incl_tax'))
    for row in (first,second,other):
        current=invoices.read(db,row.id)
        invoices.save(db,row.id,invoices.InvoiceWrite(version=current['version'],invoice_status='issued',proofs='该项目发票备注'),actor.id)
    path=f'/invoice-parties/clients/{clients[0].id}/records'
    pages=[http.get(path,params={'required':True,'invoice_status':'issued','skip':skip,'limit':1}).json() for skip in (0,1)]
    assert all(page['total']==2 for page in pages)
    assert {page['items'][0]['id'] for page in pages}=={str(first.id),str(second.id)}
    assert pages[0]['summary']=={'projects':4,'required':3,'issued':2,'partial':0,'unissued':2,'not_required':1}
    assert pages[0]['items'][0]['invoice_proofs']=='该项目发票备注'
    assert http.get(path,params={'required':False}).json()['items'][0]['id']==str(no_need.id)
    assert http.get(f'/translation-customer-finance/project/{first.id}/invoice').json()['client_id']==str(clients[0].id)
