"""对账单与开票工作流共用的项目来源适配；请求之间不共享模块状态。"""
from contextvars import ContextVar
from copy import deepcopy
from types import SimpleNamespace
from typing import Literal
from fastapi import Query
from uuid import UUID

MODULE=ContextVar('finance_source_module',default='interpretation')


async def select_module(module:Literal['interpretation','annotation','recruitment']=Query('interpretation')):
    token=MODULE.set(module)
    try:yield module
    finally:MODULE.reset(token)


def owner(db,target):
    if MODULE.get()=='interpretation':
        import interpretation_customer_finance as finance
        return finance.owner(db,'project',target)
    import project_customer_finance as source
    return source.owner(db,MODULE.get(),target)


def record(db,target):
    if MODULE.get()=='interpretation':
        import interpretation_customer_finance as finance
        return finance.record(db,'project',target)
    import business_finance as business
    return business.record(db,MODULE.get(),target)


def context(db,entity,row=None):
    if MODULE.get()=='interpretation':
        import interpretation_customer_finance as finance
        return finance.finance_context('project',entity,True,row or record(db,entity.id))
    import business_finance as business
    return business.context(db,MODULE.get(),entity,stored=row)


def model():
    if MODULE.get()=='interpretation':
        from interpretation_models import InterpretationProject
        return InterpretationProject
    from project_customer_finance import MODELS
    return MODELS[MODULE.get()]


def billing_month(project,payload):
    if MODULE.get()=='interpretation':
        from interpretation_statements import billing_month
        return billing_month(project,payload)
    from business_finance import month
    return month(project,payload)


def lines(project,payload,basis):
    if MODULE.get()=='interpretation':
        from interpretation_statements import project_rows
        return project_rows(project,payload,basis)
    import business_finance as business
    value=business.normalized(MODULE.get(),project,payload)
    rows=[]
    for index,item in enumerate(value['rates']):
        amount=item.get('amount');qty=item.get('quantity')
        from decimal import Decimal, ROUND_HALF_UP
        subtotal=format((Decimal(str(amount))*Decimal(str(qty))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP),'.2f') if amount is not None and qty is not None else None
        rows.append(dict(root_id=str(project.id),task_id=str(project.id),line_id=f'{project.id}:{index}',order_no=project.order_no,
                         customer_order_no=getattr(project,'customer_order_no','') or '',project_name=project.project_name,received_date=None,
                         language_pair=item['direction'],quantity=qty,basis=item['unit'],unit_price=amount,unit_label={'legacy':'税口径未确认','incl_tax':'含税','excl_tax':'不含税'}[basis],
                         currency=item['currency'],subtotal=subtotal,remarks=payload['settlement'].get('customer_explanation','')))
    from interpretation_statements import project_rows
    # 共用结算调整算法，保留原明细的工作量及其未填写状态。
    final=business.totals(value)['adjusted_totals' if basis=='legacy' else 'totals_'+basis]
    from decimal import Decimal
    for code,amount in final.items():
        matching=[row for row in rows if row['currency']==code]
        if matching and all(row['subtotal'] is not None for row in matching):
            difference=Decimal(amount)-sum((Decimal(row['subtotal']) for row in matching),Decimal(0))
            if difference:rows.append({**matching[0],'line_id':f'{project.id}:adjustment','basis':'结算调整','quantity':None,'unit_price':None,'subtotal':format(difference,'.2f')})
    return rows


def template(db,target,month):
    if MODULE.get()=='interpretation':
        from interpretation_statements import build
        return build(db,target,month,'settlement')
    import customer_statements as statements
    from annotation_progress_time import business_now
    project=owner(db,target);client=project.sub_client or project.client
    private=statements.private_statement_settings_available()
    settings=statements.settings_value(*statements.statement_company_settings(db)) if private else {}
    return dict(module=MODULE.get(),company=statements.COMPANY,title={'annotation':'标注','recruitment':'招聘'}[MODULE.get()]+'对账单',client_name=client.client_name if client else '',month=month,
                issue_date=business_now().date().isoformat(),tax_included=False,scope='settlement',rows=[],totals={},pending=[],settings={key:settings[key] for key in statements.PAYMENT_ACCOUNT_FIELDS} if private else {},stamp_image=(settings['stamp_image'] or settings['default_stamp']) if private else None)
