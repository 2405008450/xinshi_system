"""发票三入口共享记录、自动需求及三类说明；不连接业务数据库。"""
from tests.test_chat_participant_access import environment
from tests.test_customer_statements import context,project
import translation_customer_finance as finance
import translation_document_requirements as documents
import translation_project_invoices as invoices
import translation_finance_audit as audit
from io import BytesIO
from zipfile import ZipFile
import pytest
from PIL import Image
from routers.editor_screenshots import router as attachment_router


@pytest.mark.parametrize('extension', ['pdf', 'ofd'])
def test_invoice_file_upload_save_and_download(context, extension):
    http, db, clients, permissions, _ = context
    http.app.include_router(finance.router)
    http.app.include_router(attachment_router)
    row = project(db, clients[0], 'INV-PDF', fixed=True)
    invoice_url = f'/translation-customer-finance/project/{row.id}/invoice'
    upload_url = f'/editor-screenshots/invoice-{extension}'
    buffer = BytesIO()
    if extension == 'pdf':
        Image.new('RGB', (32, 32), 'white').save(buffer, 'PDF')
    else:
        with ZipFile(buffer, 'w') as archive:
            archive.writestr('OFD.xml', '<ofd:OFD xmlns:ofd="http://www.ofdspec.org/2016" />')
    content = buffer.getvalue()
    files = {'file': (f'发票.{extension.upper()}', content, 'application/octet-stream')}
    assert http.post(upload_url, files=files).status_code == 403
    permissions.add('projects:write')
    assert http.post(upload_url, files={'file': (f'发票.{extension}', b'invalid file', f'application/{extension}')}).status_code == 422
    uploaded = http.post(upload_url, files=files)
    assert uploaded.status_code == 201
    attachment = uploaded.json()
    proofs = f"开票备注\n![截图]({attachment['reference']})"
    saved = http.put(invoice_url, json={
        'version': http.get(invoice_url).json()['version'], 'invoice_status': 'issued', 'proofs': proofs,
    })
    assert saved.status_code == 200
    assert http.get(invoice_url).json()['proofs'] == proofs
    downloaded = http.get(f"/editor-screenshots/{attachment['id']}")
    assert downloaded.headers['content-type'] == f'application/{extension}'
    assert downloaded.headers['content-disposition'] == f'attachment; filename="invoice.{extension}"'
    assert downloaded.content == content


def test_statement_customer_filter_matches_whole_customers_before_pagination(context):
    http, db, clients, _, actor = context
    http.app.include_router(finance.router)
    required = project(db, clients[0], 'STATEMENT-1', month='2026-10')
    same_customer = project(db, clients[0], 'STATEMENT-2')
    other_customer = project(db, clients[1], 'STATEMENT-3')
    for row, need in [(required, True), (same_customer, False), (other_customer, False)]:
        documents.save(db, row, statement_required=need, actor_id=actor.id)
    db.commit()
    url = '/translation-customer-finance/page'
    for mode, expected in [('include', {str(required.id), str(same_customer.id)}),
                           ('exclude', {str(other_customer.id)})]:
        pages = [http.get(url, params={'statement_customers':mode, 'limit':1, 'skip':skip}).json()
                 for skip in range(len(expected))]
        assert all(page['total'] == len(expected) for page in pages)
        assert {page['items'][0]['id'] for page in pages} == expected
    result = http.get(url, params={'billing_month':'2026-11', 'client_ids':str(clients[0].id),
                                  'statement_customers':'include'}).json()
    assert [item['id'] for item in result['items']] == [str(same_customer.id)]


def test_document_notes_preserve_quotation_and_are_versioned(context):
    _,db,clients,_,actor=context;row=project(db,clients[0],'NOTES',fixed=True)
    current=finance.read(db,row.id)
    saved=finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,documents_only=True,
        document_notes={'quotation':'报价说明','statement':'账单说明','invoice':'发票说明'}))
    assert saved['item']['document_notes']['invoice']=='发票说明'
    assert saved['version']!=current['version']
    assert documents.quotation(db,row)['document']['items']
    quote=documents.QuotationDraft(items=[documents.QuotationLine(description='翻译费')])
    documents.save(db,row,quotation_draft=quote,actor_id=actor.id);db.commit();db.expire_all()
    assert finance.read(db,row.id)['item']['document_notes']['quotation']=='报价说明'
    assert '_document_notes' not in documents.quotation(db,row)['document']


def test_invoice_entry_reuses_status_and_proofs_and_filters_before_paging(context):
    http,db,clients,permissions,actor=context;http.app.include_router(finance.router);permissions.add('projects:write')
    first=project(db,clients[0],'INV-A',fixed=True);second=project(db,clients[0],'INV-B',fixed=True)
    empty=project(db,clients[0],'INV-C',fixed=True)
    for row in (first,second):
        current=finance.read(db,row.id)
        finance.save(db,actor,row.id,finance.PriceWrite(version=current['version'],order_id=row.id,pricing_mode='fixed',adjusted_total=500,
            adjusted_total_incl_tax=530,billing_tax_mode='incl_tax'))
        state=http.get(f'/translation-customer-finance/project/{row.id}/invoice').json()
        assert state['required'] and state['tax_mode']=='incl_tax'
        result=http.put(f'/translation-customer-finance/project/{row.id}/invoice',json={'version':state['version'],'invoice_status':'issued','proofs':'发票附件备注'})
        assert result.status_code==200,result.text
        assert result.json()['proofs']=='发票附件备注'
        reloaded=invoices.read(db,row.id)
        assert reloaded['invoice_status']=='issued'
        assert http.put(f'/translation-customer-finance/project/{row.id}/invoice',json={'version':state['version'],'invoice_status':'partial'}).status_code==409
        assert audit.history(db,row.id)['items'][0]['after']['invoice_data']['invoice_status']=='issued'
    params={'include_invoice_status':True,'invoice_status':'issued','limit':1}
    pages=[http.get('/translation-customer-finance/page',params={**params,'skip':skip}).json() for skip in (0,1)]
    assert all(page['total']==2 for page in pages)
    assert {page['items'][0]['id'] for page in pages}=={str(first.id),str(second.id)}
    assert all(page['items'][0]['invoice_status']=='issued' for page in pages)
    assert not invoices.read(db,empty.id)['required']

    for number in ('INV-D', 'INV-E'):
        excluded = project(db, clients[0], number, fixed=True)
        current = finance.read(db, excluded.id)
        finance.save(db, actor, excluded.id, finance.PriceWrite(
            version=current['version'], order_id=excluded.id, pricing_mode='fixed',
            adjusted_total=500, billing_tax_mode='excl_tax',
        ))
    params['invoice_status'] = 'not_required'
    pages = [http.get('/translation-customer-finance/page', params={**params, 'skip': skip}).json() for skip in (0, 1)]
    assert all(page['total'] >= 2 and page['items'][0]['invoice_required'] is False for page in pages)
    assert pages[0]['items'][0]['id'] != pages[1]['items'][0]['id']

    unknown = project(db, clients[0], 'INV-F', fixed=True)
    charge = unknown.customer_charge_items[0]
    charge.total_excl_tax = charge.total_incl_tax = None
    db.commit()
    for requirement, expected, total in [('yes', True, 2), ('no', False, 3), ('unknown', None, 1)]:
        result = http.get('/translation-customer-finance/page', params={
            'include_invoice_status': True, 'invoice_required': requirement, 'limit': 1,
        }).json()
        assert result['total'] == total
        assert result['items'][0]['invoice_required'] is expected
    result = http.get('/translation-customer-finance/page', params={
        'include_invoice_status': True, 'invoice_required': 'no', 'invoice_status': 'issued',
    }).json()
    assert result['total'] == 0 and result['items'] == []


def test_invoice_write_requires_permission_and_does_not_pollute_quotation(context):
    http,db,clients,permissions,actor=context;http.app.include_router(finance.router)
    row=project(db,clients[0],'INV-PERM',fixed=True)
    state=invoices.read(db,row.id)
    route=f'/translation-customer-finance/project/{row.id}/invoice'
    assert http.put(route,json={'version':state['version'],'invoice_status':'issued'}).status_code==403
    permissions.add('projects:write')
    assert http.put(route,json={'version':state['version'],'invoice_status':'issued','proofs':'screenshot://00000000-0000-0000-0000-000000000000'}).status_code==422
    assert http.put(route,json={'version':state['version'],'invoice_status':'issued','proofs':'开票备注'}).status_code==200
    documents.save(db,row,document_notes=documents.DocumentNotes(invoice='保留发票说明'),actor_id=actor.id);db.commit()
    documents.save(db,row,quotation_draft=documents.QuotationDraft(items=[documents.QuotationLine(description='新版报价')]),actor_id=actor.id);db.commit()
    quote=documents.quotation(db,row)['document']
    assert '_invoice' not in quote and quote['items']
    assert invoices.read(db,row.id)['proofs']=='开票备注'
