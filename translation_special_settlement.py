"""特殊结算的单据和税口径独立于项目收费。"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from annotation_progress_time import business_now
from translation_document_requirements import TranslationProjectDocuments, ready


class SettingsWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: UUID
    apply_to_order: bool = False
    statement_required: bool | None = None
    tax_mode: Literal['incl_tax', 'excl_tax'] | None = None
    invoice_status: Literal['unissued', 'partial', 'issued'] | None = None
    invoice_sent: bool | None = None


def settings_by_project(db, project_ids):
    if not project_ids or not ready(db):
        return {}
    return {key: (data or {}).get('_special_settlement', {}) for key, data in
            db.query(TranslationProjectDocuments.project_id, TranslationProjectDocuments.quotation_data)
            .filter(TranslationProjectDocuments.project_id.in_(project_ids))}


def order_nodes(node):
    yield node
    for child in node['children']:
        yield from order_nodes(child)


def billing_totals(node, *, tax_mode=None):
    if not node.get('price_aggregate'):
        mode = node['special_tax_mode']
        if tax_mode is not None and mode != tax_mode:
            return {}
        fields = {'incl_tax': 'totals_incl_tax', 'excl_tax': 'totals_excl_tax'}
        return node.get(fields.get(mode), {})
    if tax_mode is None:
        totals = {}
        for mode in ('excl_tax', 'incl_tax'):
            for currency, amount in billing_totals(node, tax_mode=mode).items():
                totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(amount))
        return totals
    totals = {}
    for child in node['children']:
        for currency, amount in billing_totals(child, tax_mode=tax_mode).items():
            totals[currency] = totals.get(currency, Decimal(0)) + Decimal(str(amount))
    adjustment = node.get('total_adjustment') or {}
    currency = adjustment.get('currency')
    if node['special_tax_mode'] == tax_mode or totals:
        if tax_mode in adjustment:
            totals[currency] = Decimal(adjustment[tax_mode])
        elif currency in totals and (discount := adjustment.get(tax_mode.replace('_tax','_discount'))) is not None:
            totals[currency] = (totals[currency] * discount / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return totals


def invoice_state(settings):
    status = settings.get('invoice_status', 'unissued')
    sent = settings.get('customer_sent')
    return {
        'invoice_status': status,
        'proofs': settings.get('proofs', ''),
        'issued_by': settings.get('issued_by'),
        'issued_notification': settings.get('issued_notification'),
        'customer_sent': (sent or {'name': '—', 'at': None})
        if status == 'issued' and settings.get('invoice_sent') else None,
    }


def update_order_data(document, order_id, values, actor_id, moment):
    data = dict(document.quotation_data or {})
    settings = dict(data.get('_special_settlement', {}))
    settings[str(order_id)] = {**settings.get(str(order_id), {}), **values}
    document.quotation_data = {**data, '_special_settlement': settings}
    document.updated_by = actor_id
    document.updated_at = moment


def apply_settings(node, settings, parent=None):
    override = settings.get(node['id'], {})
    defaults = parent or {}
    tax = override.get('tax_mode', defaults.get('tax_mode'))
    required = override.get('statement_required', defaults.get('statement_required'))
    selected_tax = tax or node.get('effective_billing_tax_mode')
    node['special_tax_mode'] = selected_tax
    node['special_invoice_status'] = override.get('invoice_status', 'unissued')
    node['special_invoice_sent'] = override.get('invoice_sent', False)
    node['original_invoice_required'] = node.get('invoice_required')
    if required is not None:
        node['statement_required'] = required
    node['invoice_required'] = selected_tax == 'incl_tax' if selected_tax in ('incl_tax', 'excl_tax') else None
    for child in node['children']:
        apply_settings(child, settings, {'tax_mode': tax, 'statement_required': required})
    if node.get('price_aggregate'):
        modes = {child['special_tax_mode'] for child in node['children']}
        node['special_tax_mode'] = next(iter(modes)) if len(modes) == 1 else 'mixed' if modes else selected_tax
        invoices = {child['invoice_required'] for child in node['children']}
        if invoices:
            node['invoice_required'] = True if True in invoices else None if None in invoices else False
    node['has_statement_required_orders'] = any(child['statement_required'] or child['has_statement_required_orders']
                                                for child in node['children'])
    node['special_invoice_required'] = node['invoice_required']


def save(db, project, order_ids, data, actor_id):
    if not ready(db):
        raise HTTPException(503, '项目单据存储尚未初始化')
    values = data.model_dump(exclude={'order_id', 'apply_to_order'}, exclude_none=True)
    if not values:
        raise HTTPException(422, '请选择要调整的特殊结算字段')
    row = db.query(TranslationProjectDocuments).filter_by(project_id=project.id).with_for_update().populate_existing().first()
    if row is None:
        row = TranslationProjectDocuments(project_id=project.id, quotation_revision=0)
        db.add(row)
    stored = dict(row.quotation_data or {})
    settings = dict(stored.get('_special_settlement', {}))
    if values.keys() & {'invoice_status', 'invoice_sent'}:
        if data.apply_to_order:
            raise HTTPException(422, '开票记录请按订单登记')
        previous = settings.get(str(data.order_id), {})
        status = values.get('invoice_status', previous.get('invoice_status', 'unissued'))
        if data.invoice_sent and status != 'issued':
            raise HTTPException(422, '请先标记已开票')
        if status != 'issued':
            values.update(invoice_sent=False, customer_sent=None, issued_by=None, issued_notification=None)
        elif data.invoice_sent is not None:
            from models import AppUser
            from translation_project_invoices import action_value
            values['customer_sent'] = action_value(db.get(AppUser, actor_id), business_now()) if data.invoice_sent else None
    for order_id in (order_ids if data.apply_to_order else [str(data.order_id)]):
        settings[order_id] = {**settings.get(order_id, {}), **values}
    row.quotation_data = {**stored, '_special_settlement': settings}
    row.updated_by = actor_id
    row.updated_at = business_now()
