"""笔译客户经营统计，只读；复用财务树，不重复计算母子订单。"""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import re
from fastapi import HTTPException
from sqlalchemy.orm import joinedload, selectinload
from models import TranslationProject as Project, TranslationSubOrder as Child, Client, SubClient
from annotation_progress_time import business_datetime, business_now
from search_matching import matches_keywords


def order_date(number):
    match=re.match(r'^TP-(\d{8}|\d{6})-',str(number or '').upper())
    if not match:return None
    digits=match[1]
    if len(digits)==6:digits='20'+digits
    try:return date(int(digits[:4]),int(digits[4:6]),int(digits[6:8]))
    except ValueError:return None


def period_bounds(day,granularity):
    if granularity=='day':return day,day
    if granularity=='week':
        start=day-timedelta(days=day.weekday());return start,start+timedelta(days=6)
    start=day.replace(day=1);end=(start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1))-timedelta(days=1)
    return start,end


def percentage(value,total):return float((Decimal(value)*100/total).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if total else 0

def summarize(records,first_dates,start,end,granularity,tax_basis):
    periods={};customers={}
    cursor=period_bounds(start,granularity)[0]
    while cursor<=end:
        left,right=period_bounds(cursor,granularity)
        periods[left]=dict(period_start=left.isoformat(),period_end=right.isoformat(),range_start=max(left,start).isoformat(),range_end=min(right,end).isoformat(),order_count=0,_clients=set(),_new=set(),new_order_count=0,old_order_count=0,unknown_order_count=0,_money={})
        cursor=right+timedelta(days=1)
    for record in records:
        day=record['day']
        if not start<=day<=end:continue
        left,right=period_bounds(day,granularity);period=periods[left]
        key=record['client_key'];first=first_dates.get(key) if key else None
        cohort='unknown' if not first else 'new' if left<=first<=right else 'old'
        period['order_count']+=1;period[cohort+'_order_count']+=1
        if key:
            period['_clients'].add(key)
            if cohort=='new':period['_new'].add(key)
        customer=customers.setdefault((left,key),dict(period_start=left.isoformat(),period_end=right.isoformat(),client_id=key,client_name=record['client_name'],client_short_name=record['client_short_name'],first_order_date=first.isoformat() if first else None,cohort=cohort,order_count=0,missing_amount_orders=0,partial_amount_orders=0,_money={}))
        customer['order_count']+=1
        node=record['finance'];amounts=node.get('totals_'+tax_basis,{})
        incomplete=not amounts or any(not item.get('totals_'+tax_basis) for item in leaves(node))
        if not amounts:customer['missing_amount_orders']+=1
        elif incomplete:customer['partial_amount_orders']+=1
        for currency,amount in amounts.items():
            for target in (customer,period):
                money=target['_money'].setdefault(currency,dict(total=Decimal(0),order_count=0,complete_order_count=0,complete_total=Decimal(0)))
                money['total']+=Decimal(str(amount));money['order_count']+=1
                if not incomplete:money['complete_total']+=Decimal(str(amount));money['complete_order_count']+=1
    def money_rows(values):
        return [dict(currency=currency,total_amount=str(row['total'].quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),priced_order_count=row['order_count'],complete_order_count=row['complete_order_count'],average_amount=str((row['complete_total']/row['complete_order_count']).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if row['complete_order_count'] else None) for currency,row in sorted(values.items())]
    output=[]
    for period in periods.values():
        count=len(period.pop('_clients'));new=len(period.pop('_new'));total=period['order_count']
        period.update(customer_count=count,new_customer_count=new,old_customer_count=count-new,new_customer_share=percentage(new,count),old_customer_share=percentage(count-new,count),new_order_share=percentage(period['new_order_count'],total),old_order_share=percentage(period['old_order_count'],total),unknown_order_share=percentage(period['unknown_order_count'],total),amounts=money_rows(period.pop('_money')))
        output.append(period)
    detail=[]
    for customer in customers.values():
        period=periods[date.fromisoformat(customer['period_start'])]
        customer.update(order_share=percentage(customer['order_count'],period['order_count']),amounts=money_rows(customer.pop('_money')));detail.append(customer)
    detail.sort(key=lambda row:(row['period_start'],row['client_short_name'],row['client_id'] or ''))
    return dict(periods=output,customers=detail)


def leaves(node):
    if not node.get('children'):yield node
    for child in node.get('children',[]):yield from leaves(child)


def report(db,*,start,end,granularity='month',date_basis='order',tax_basis='excl_tax',client_keyword=''):
    if start>end:raise HTTPException(422,'开始日期不能晚于结束日期')
    if (end-start).days>1095:raise HTTPException(422,'单次统计范围请控制在三年以内')
    # 全历史轻量元数据用于首次下单判断，不能只在当前筛选内寻找“新客户”。
    clients={row.id:row for row in db.query(Client.id,Client.client_name,Client.client_short_name,Client.client_code).all()}
    metadata=db.query(Project.id,Project.order_no,Project.client_id,SubClient.parent_client_id,Project.created_at,Project.customer_reception_time).outerjoin(SubClient,Project.sub_client_id==SubClient.id).filter(Project.annotation_migrated_at.is_(None)).all()
    first_dates={};selected=[];missing_date=0;fallback_date=0
    for row in metadata:
        day=order_date(row.order_no) if date_basis=='order' else business_datetime(row.customer_reception_time).date() if row.customer_reception_time else None
        fallback=day is None
        if fallback and row.created_at:day=business_datetime(row.created_at).date()
        if day is None:missing_date+=1;continue
        client_id=row.client_id or row.parent_client_id;key=str(client_id) if client_id else None;client=clients.get(client_id)
        if key:first_dates[key]=min(first_dates.get(key,day),day)
        if not start<=day<=end:continue
        name=(client.client_name or client.client_short_name or '未命名客户') if client else '未关联客户'
        short=(client.client_short_name or name) if client else name
        if not matches_keywords(' '.join([name,short,client.client_code or '' if client else '']),client_keyword):continue
        if fallback:fallback_date+=1
        selected.append(dict(id=row.id,day=day,client_key=key,client_name=name,client_short_name=short))
    # 批量加载本期订单树、计价及统计；不逐项目查询人员或客户。
    projects={}
    for offset in range(0,len(selected),400):
        rows=db.query(Project).options(joinedload(Project.client),joinedload(Project.sub_client),selectinload(Project.customer_charge_items),selectinload(Project.sub_orders).selectinload(Child.customer_charge_items)).filter(Project.id.in_([row['id'] for row in selected[offset:offset+400]])).all()
        projects.update({row.id:row for row in rows})
    import crud,customer_translation_rates as rates,translation_quantity_basis as basis
    from translation_customer_finance import tree
    crud._attach_word_count_matrices(db,projects=list(projects.values()))
    ids=[charge.id for project in projects.values() for owner in [project,*project.sub_orders] for charge in owner.customer_charge_items]
    rates.metadata(db,ids);basis.metadata(db,ids)
    for record in selected:
        project=projects[record['id']];project.client_name=record['client_name'];project.client_short_name=record['client_short_name']
        record['finance']=tree(project,summary_only=True)['item']
    result=summarize(selected,first_dates,start,end,granularity,tax_basis)
    return dict(**result,generated_at=business_now().isoformat(),start=start.isoformat(),end=end.isoformat(),granularity=granularity,date_basis=date_basis,tax_basis=tax_basis,fallback_date_orders=fallback_date,undated_orders=missing_date,order_count=len(selected))
