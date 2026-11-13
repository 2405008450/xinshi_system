"""按已登记的口译收费生成项目及客户月度对账单。"""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func

from annotation_progress_time import business_datetime, business_now
import customer_statements as statements
import interpretation_customer_finance as finance
from interpretation_models import InterpretationProject
from models import SubClient


def order_day(project):
    match = re.match(r'^IP-(\d{8}|\d{6})-', project.order_no or '')
    if match:
        digits = match[1] if len(match[1]) == 8 else '20' + match[1]
        try:
            return date.fromisoformat(f'{digits[:4]}-{digits[4:6]}-{digits[6:]}')
        except ValueError:
            pass
    fallback = project.customer_confirmation_time or project.customer_consultation_time or project.created_at
    return business_datetime(fallback).date() if fallback else None


def project_rows(project, payload, basis):
    setting = finance.settlement(payload)
    day = order_day(project)
    label = {'legacy': '税口径未确认', 'excl_tax': '不含税', 'incl_tax': '含税'}[basis]
    rows = []

    def add(currency, workload, subtotal=None, *, quantity=None, unit=None, direction='-'):
        rows.append(dict(order_no=project.order_no, root_id=str(project.id), task_id=str(project.id),
                         line_id=f'{project.id}:{len(rows)}', customer_order_no=project.customer_order_no or '',
                         received_date=day.isoformat() if day else None, project_name=project.project_name or project.order_no,
                         language_pair=direction, quantity=quantity, basis=workload, unit_price=unit,
                         unit_label=label, currency=currency, subtotal=statements.money(subtotal),
                         remarks=setting.customer_explanation))

    for rate in payload.get('rates', []):
        tax = rate.get('tax_prices') or {}
        quantity = rate['quantity']
        unit = rate['amount'] if basis == 'legacy' else tax.get('unit_price_' + basis)
        total = None if basis == 'legacy' else tax.get('total_' + basis)
        if total is None and unit is not None:
            total = Decimal(str(unit)) * Decimal(str(quantity))
        workload = rate['unit']
        if rate.get('hours'):
            workload += f"（每{rate['unit']} {rate['hours']} 小时"
            workload += '，含午餐）' if rate.get('includes_lunch') else '）'
        add(rate['currency'], workload, total, quantity=str(quantity), unit=unit, direction=rate['direction'])
    overtime = payload.get('overtime') if payload.get('has_overtime') else None
    if overtime:
        value = overtime['amount'] if basis == 'legacy' else (overtime.get('tax_prices') or {}).get('total_' + basis)
        add(overtime['currency'], '加班费', value)
    for item in payload.get('adjusted_totals', []):
        value = item['amount'] if basis == 'legacy' else (item.get('tax_prices') or {}).get('total_' + basis)
        if value is None:
            continue
        matching = [row for row in rows if row['currency'] == item['currency']]
        if matching and all(row['subtotal'] is not None for row in matching):
            difference = Decimal(str(value)) - sum(Decimal(row['subtotal']) for row in matching)
            if difference:
                add(item['currency'], '总价调整', difference)
        else:
            for row in matching:
                row['counted_in_total'] = False
            add(item['currency'], '调整后总价', value)
    if not rows:
        add('CNY', '待登记收费')
    return rows


def build(db, target: UUID, month, scope, basis=None):
    if not finance.ready(db):
        raise HTTPException(503, '口译财务存储尚未初始化')
    project = finance.owner(db, 'project', target)
    client = project.client or (project.sub_client.parent_client if project.sub_client else None)
    if scope == 'customer' and not client:
        raise HTTPException(422, '请先为项目关联客户')
    projects = [project] if scope == 'project' else db.query(InterpretationProject).outerjoin(
        SubClient, InterpretationProject.sub_client_id == SubClient.id).filter(
        func.coalesce(InterpretationProject.client_id, SubClient.parent_client_id) == client.id
    ).order_by(InterpretationProject.order_no).all()
    records, _ = finance.finance_records(db, projects, True)
    rows, pending = [], []
    for item in projects:
        row = records.get(item.id)
        payload = row.payload if row else {}
        day = order_day(item)
        setting = finance.settlement(payload)
        billing_month = setting.billing_month or (day.strftime('%Y-%m') if day else None)
        if billing_month != month:
            continue
        lines = project_rows(item, payload, basis or setting.tax_basis)
        if any(line['subtotal'] is None and line.get('counted_in_total', True) for line in lines):
            pending.append(f'{item.order_no} 收费金额待补')
        rows.extend(lines)
        if len(rows) > 10000:
            raise HTTPException(422, '对账单超过10000条明细，请缩小范围')
    totals = {}
    for row in rows:
        if row['subtotal'] is not None and row.get('counted_in_total', True):
            code = row['currency']
            totals[code] = totals.get(code, Decimal(0)) + Decimal(row['subtotal'])
    subject = db.get(statements.CustomerStatementCompany, 'company')
    private = statements.private_statement_settings_available()
    settings = statements.settings_value(db.get(statements.CustomerStatementSettings, 'company'), subject) if private else {}
    result = dict(company=subject.company if subject else statements.COMPANY, title='口译对账单',
                  client_name=(client.client_name or client.client_short_name) if client else (project.client_full_name or project.client_short_name or ''),
                  month=month, issue_date=business_now().date().isoformat(), scope=scope,
                  tax_included={row['unit_label'] for row in rows} == {'含税'},
                  rows=rows, totals={code: statements.money(amount) for code, amount in totals.items()},
                  pending=pending, module='interpretation', private_settings_available=private,
                  settings={key: settings[key] for key in statements.PAYMENT_ACCOUNT_FIELDS} if private else {},
                  stamp_image=(settings['stamp_image'] or settings['default_stamp']) if private else None)
    result['statement_version'] = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return result
