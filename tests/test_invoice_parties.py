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


def test_batch_invoice_delivery_and_receipts(context):
    from io import BytesIO
    from uuid import uuid4
    from PIL import Image
    from sqlalchemy import event
    from department_models import Department
    from models import AppNotification, AppUser
    from routers import auth
    from routers.editor_screenshots import router as attachments
    import invoice_workflow as workflow

    http, db, clients, permissions, sender = setup(context)
    http.app.include_router(workflow.router)
    http.app.include_router(attachments)
    permissions.update(('projects:write', 'system:users:write'))
    receiver = AppUser(id=uuid4(), username='invoice_qa_xiong', full_name='熊旺', password_hash='unused', department='客户部', is_active=True)
    db.add_all([receiver, Department(name='客户部')])
    db.commit()
    @event.listens_for(db, 'before_flush')
    def emulate_postgres_user_id(session, _context, _instances):
        for user in session.new:
            if isinstance(user, AppUser) and user.id is None:
                user.id = uuid4()
    created = http.post('/invoice-workflow/settings/test-recipient', json={'password':'Invoice-Test-Password-123'})
    assert created.status_code == 201, created.text
    test_account = db.query(AppUser).filter_by(username=workflow.TEST_RECIPIENT_USERNAME).one()
    assert test_account.department == '客户部'

    project_ids = []
    for number, client, currency, amount in [
        ('BATCH-A', clients[0], 'CNY', '530.10'),
        ('BATCH-B', clients[1], 'CNY', '530.00'),
        ('BATCH-C', clients[0], 'CNY', '123.45'),
        ('BATCH-D', clients[0], 'USD', '25.00'),
    ]:
        row = project(db, client, number, fixed=True, currency=currency)
        current = finance.read(db, row.id)
        finance.save(db, sender, row.id, finance.PriceWrite(version=current['version'], order_id=row.id,
            pricing_mode='fixed', currency=currency, adjusted_total=500, adjusted_total_incl_tax=amount, billing_tax_mode='incl_tax'))
        project_ids.append(str(row.id))
    preview = http.post('/invoice-workflow/requests/preview', json={'project_ids':project_ids}).json()
    groups = preview['customer_groups']
    assert groups == [
        {'client_id': str(clients[0].id), 'project_ids': [project_ids[0], project_ids[2], project_ids[3]],
         'totals': {'CNY': '653.55', 'USD': '25.00'}},
        {'client_id': str(clients[1].id), 'project_ids': [project_ids[1]], 'totals': {'CNY': '530.00'}},
    ]
    assert {person['id'] for person in preview['recipients']} == {str(receiver.id), str(test_account.id)}
    payload = {'project_ids':project_ids, 'subject_key':'shenzhen', 'invoice_type':'electronic_special',
        'tax_rate':6, 'settings_revision':preview['settings_revision'],
        'expected_user_ids':[person['id'] for person in preview['recipients']], 'idempotency_key':str(uuid4()), 'note':'测试开票说明'}
    assert http.post('/invoice-workflow/requests/batch', json=payload).status_code == 422
    payload['tax_rate'] = 3
    result = http.post('/invoice-workflow/requests/batch', json=payload)
    assert result.status_code == 200, result.text
    request_id = result.json()['id']
    assert http.post('/invoice-workflow/requests/batch', json=payload).json()['id'] == request_id
    assert db.query(AppNotification).filter_by(notification_type='invoice_request').count() == 2

    url = f'/invoice-workflow/requests/{request_id}'
    http.app.dependency_overrides[auth.get_current_user] = lambda: test_account
    permissions.clear()
    request = http.get(url).json()
    assert request['is_recipient']
    assert request['customer_groups'] == groups
    for _ in range(2):
        assert http.post(url + '/receipts', json={}).status_code == 200
    assert db.query(AppNotification).filter_by(notification_type='invoice_receipt').count() == 1
    invoice_url = f'{url}/projects/{project_ids[0]}/invoice'
    invoice = http.get(invoice_url).json()
    buffer = BytesIO()
    Image.new('RGB', (16, 16), 'white').save(buffer, 'PDF')
    attachment = http.post('/editor-screenshots/invoice-pdf', data={'request_id':request_id},
        files={'file':('invoice.pdf', buffer.getvalue(), 'application/pdf')})
    assert attachment.status_code == 201, attachment.text
    proof = f"![截图]({attachment.json()['reference']})"
    saved = http.put(invoice_url, json={'version':invoice['version'], 'invoice_status':'issued','proofs':proof})
    assert saved.status_code == 200, saved.text
    delivery_url = f'{url}/projects/{project_ids[0]}/deliver'
    for _ in range(2):
        delivered = http.post(delivery_url, json={'version':saved.json()['version']})
        assert delivered.status_code == 200, delivered.text
    assert db.query(AppNotification).filter_by(notification_type='invoice_delivered', recipient_user_id=sender.id).count() == 1

    http.app.dependency_overrides[auth.get_current_user] = lambda: sender
    permissions.update(('projects:read', 'projects:write'))
    finance_url = f'/translation-customer-finance/project/{project_ids[0]}/invoice'
    issued = http.get(finance_url).json()
    assert issued['issued_by']['name'] == test_account.full_name
    assert issued['issued_notification']['at'].endswith('+08:00')
    marked = http.put(finance_url + '/customer-sent', json={'sent':True})
    assert marked.status_code == 200
    action = marked.json()['customer_sent']
    assert action['name'] == sender.full_name and action['at'].endswith('+08:00')
    assert http.put(finance_url + '/customer-sent', json={'sent':True}).json()['customer_sent'] == action
    rows = http.get('/translation-customer-finance/page', params={'include_invoice_status':True,
                    'payment_project_id':project_ids[0]}).json()['items']
    assert rows[0]['customer_sent'] == action and rows[0]['issued_notification'] == issued['issued_notification']
    received = http.post(url + '/receipts', json={'project_id':project_ids[0]})
    assert received.status_code == 200
    delivery = received.json()['snapshot']['deliveries'][project_ids[0]]
    assert delivery['proofs'] == proof and delivery['receipt']['at'].endswith('+08:00')
    assert db.query(AppNotification).filter_by(notification_type='invoice_receipt', recipient_user_id=test_account.id).count() == 1

    http.app.dependency_overrides[auth.get_current_user] = lambda: receiver
    assert http.post(url + '/receipts', json={}).status_code == 200
    second_invoice_url = f'/translation-customer-finance/project/{project_ids[1]}/invoice'
    pending = http.get(second_invoice_url).json()
    assert pending['can_notify_requester'] is True
    attached = http.post('/editor-screenshots/invoice-pdf',
        files={'file':('second.pdf', buffer.getvalue(), 'application/pdf')}).json()
    second_saved = http.put(second_invoice_url, json={'version':pending['version'], 'invoice_status':'issued',
        'proofs':f"![截图]({attached['reference']})"})
    assert second_saved.status_code == 200
    notify_url = f'/invoice-workflow/projects/{project_ids[1]}/notify-issued'
    assert http.post(notify_url, json={'version':second_saved.json()['version']}).json()['notified'] == 1
    assert http.get(second_invoice_url).json()['issued_notification']['name'] == receiver.full_name
    assert http.get(second_invoice_url).json()['can_notify_requester'] is False
