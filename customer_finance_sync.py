"""客户参考价单向自动下发；项目回写及差异覆盖均须显式确认。"""
from copy import deepcopy
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from database import get_db
from models import Client, TranslationProject, TranslationSubOrderChargeItem
from annotation_progress_time import business_now
from routers.auth import get_current_user
from permission_service import user_has_permission


def number(value):
    return str(Decimal(str(value)).normalize()) if value is not None else None


def oral_key(row):
    return (row['direction'], row['currency'], row['unit'],
            number(row.get('hours')) if row['unit'] in ('天', '半天') else None,
            bool(row.get('includes_lunch')) if row['unit'] == '天' else False)


def signature(module, rows):
    import customer_translation_rates as rates
    key = rates.rate_key if module == 'translation' else oral_key
    # 数量为项目自身的业务量，不属于客户单价，重复组合项也保留以识别歧义。
    return sorted([(str(key(row)), number(row['amount'])) for row in rows], key=str)


def oral_defaults(project, rows):
    directions = {' ↔ '.join(item.language_labels) for item in project.language_directions}
    return [{**deepcopy(row), 'quantity': '1'} for row in rows if row['direction'] in directions]


def translation_defaults(owner, project, rows):
    choices = set(str(owner.language_pair or project.language_pair or '').split('；'))
    return [dict(row, id=None, reference_id=row['id'], reference_revision=row['revision'])
            for row in rows if row['language_pair'] in choices]


def auto_translation(db, user, client_id, before, after, project_id=None):
    import customer_translation_rates as rates
    import translation_customer_finance as finance
    import translation_finance_audit as audit
    if not before and not after:return
    audit.require_ready(db)
    previous = {rates.rate_key(row): row for row in before}
    current = {rates.rate_key(row): row for row in after}
    query = db.query(TranslationProject).filter_by(client_id=client_id).filter(TranslationProject.annotation_migrated_at.is_(None))
    if project_id: query=query.filter_by(id=project_id)
    projects = query.order_by(TranslationProject.id).with_for_update().all()
    for project in projects:
        project = finance.crud.get_translation_project(db,project.id)
        captured = audit.capture(project)
        changed = False
        for owner in finance.hierarchy(project)[0]:
            rows = rates.order_rates(db, owner, owner.language_pair or project.language_pair)
            candidates = translation_defaults(owner, project, after) if not rows else rows
            by_id = {str(row.id): row for row in owner.customer_charge_items}
            for data in candidates:
                key = rates.rate_key(data)
                ref = current.get(key)
                old = previous.get(key)
                if not ref or (rows and (not old or number(data['amount']) != number(old['amount']))):
                    continue
                charge = by_id.get(data.get('id'))
                moment = business_now().replace(tzinfo=None)
                if charge is None:
                    charge = TranslationSubOrderChargeItem(id=uuid4(), translation_project_id=project.id if owner is project else None,
                        sub_order_id=None if owner is project else owner.id, sequence_no=max((item.sequence_no or 0 for item in owner.customer_charge_items),default=0)+1,
                        item_name='翻译费', pricing_mode='metric', created_at=moment)
                    owner.customer_charge_items.append(charge)
                elif number(data['amount']) == number(ref['amount']) and data.get('reference_revision') == ref['revision']:
                    continue
                charge.unit_price = charge.unit_price_excl_tax = Decimal(ref['amount'])
                charge.currency = ref['currency']; charge.metric_type = ref['metric']; charge.unit_size = Decimal(ref['unit_size'])
                charge.updated_at = moment; owner.updated_at = moment; project.updated_at = moment
                db.flush()
                meta = db.get(rates.TranslationChargeDirection, charge.id)
                if meta is None:
                    meta = rates.TranslationChargeDirection(charge_id=charge.id); db.add(meta)
                meta.language_pair = ref['language_pair']; meta.reference_id = UUID(ref['id']); meta.reference_revision = ref['revision']
                changed = True
        if changed:
            db.flush(); rates.invalidate_metadata(db); audit.append(db, user, project, captured)


def inherit_translation(db, project, user_id):
    import customer_translation_rates as rates
    import translation_finance_audit as audit
    from models import AppUser
    if not project.client_id or not user_id or not rates.ready(db) or not audit.ready(db): return
    refs=rates.library(db,project.client_id)['items']
    user=db.get(AppUser,user_id)
    if refs and user:auto_translation(db,user,project.client_id,[],refs,project.id)


def store_oral(db, user, scope, target, payload, row=None):
    import interpretation_customer_finance as oral
    row = row or oral.record(db, scope, target)
    before = deepcopy(row.payload) if row else {}
    if row is None:
        row = oral.InterpretationCustomerFinance(**{scope+'_id': target}, revision=0, payload={})
        db.add(row); db.flush()
    row.revision += 1; row.payload = deepcopy(payload)
    db.add(oral.InterpretationCustomerFinanceHistory(finance_id=row.id, revision=row.revision,
        actor_id=user.id, actor_name=user.full_name or user.username, before=before, after=deepcopy(payload)))
    db.flush()
    return row


def auto_oral(db, user, client_id, before, after):
    import interpretation_customer_finance as oral
    from interpretation_models import InterpretationProject
    previous = {oral_key(row): row for row in before}
    current = {oral_key(row): row for row in after}
    for project in db.query(InterpretationProject).filter_by(client_id=client_id).order_by(InterpretationProject.id).with_for_update().all():
        row = oral.record(db, 'project', project.id)
        payload = deepcopy(row.payload) if row else oral.FinanceWrite(revision=0).model_dump(mode='json', exclude={'revision','update_library','library_revision','sync_confirmed'})
        original = deepcopy(payload)
        if not payload['rates']:
            payload['rates'] = oral_defaults(project, after)
        else:
            for item in payload['rates']:
                key = oral_key(item)
                if key in previous and key in current and number(item['amount']) == number(previous[key]['amount']):
                    item['amount'] = current[key]['amount']
        if payload != original:
            store_oral(db, user, 'project', project.id, payload, row)


def require(db, user, code):
    if not user_has_permission(db, user.id, code) and not (code.endswith(':read') and user_has_permission(db,user.id,code.replace(':read',':write'))):
        raise HTTPException(403, '无权执行此单价同步操作')


def library(module, db, client_id):
    if module == 'translation':
        import customer_translation_rates as rates
        result = rates.library(db, client_id)
        return result['items'], result['version'], result['ready']
    import interpretation_customer_finance as oral
    result = oral.context(db, 'client', client_id)
    return result['payload']['rates'], str(result['revision']), result['ready']


def project_state(module, db, project_id, order_id):
    if module == 'translation':
        import translation_customer_finance as finance
        import customer_translation_rates as rates
        project = finance.crud.get_translation_project(db, project_id)
        if not project or project.annotation_migrated_at is not None: raise HTTPException(404, '项目不存在')
        owners, numbers, _ = finance.hierarchy(project)
        owner = next((row for row in owners if row.id == order_id), None)
        if owner is None: raise HTTPException(422, '订单不属于此项目')
        return project, owner, rates.order_rates(db, owner, owner.language_pair or project.language_pair), finance.version(project), numbers[str(owner.id)]
    import interpretation_customer_finance as oral
    project = oral.owner(db, 'project', project_id)
    if order_id != project_id: raise HTTPException(422, '订单不属于此项目')
    row = oral.record(db, 'project', project_id)
    return project, project, deepcopy(row.payload.get('rates', [])) if row else [], str(row.revision if row else 0), project.order_no


def matching(module, project, owner, rows, references):
    if module == 'translation':
        # 返回该订单全部匹配方向的参考价，使缺失的货币/口径同样构成差异。
        return translation_defaults(owner, project, references)
    return oral_defaults(project, references)


router = APIRouter(prefix='/customer-finance-sync', tags=['customer-finance-sync'])


@router.get('/{module}/{client_id}/differences')
def differences(module: Literal['translation','interpretation'], client_id: UUID,
                page: int = Query(1, ge=1), db=Depends(get_db), user=Depends(get_current_user)):
    require(db, user, 'clients:read' if user_has_permission(db, user.id, 'clients:read') else 'clients:write')
    refs, customer_version, available = library(module, db, client_id)
    if not available: return dict(ready=False, items=[], total=0)
    from interpretation_models import InterpretationProject
    model = TranslationProject if module == 'translation' else InterpretationProject
    query = db.query(model).filter_by(client_id=client_id)
    if module == 'translation': query = query.filter(model.annotation_migrated_at.is_(None))
    result = []
    for project in query.order_by(model.id).all():
        if module == 'translation':
            import translation_customer_finance as finance
            import customer_translation_rates as rates
            project=finance.crud.get_translation_project(db,project.id)
            owners,numbers,_ = finance.hierarchy(project)
            version=finance.version(project)
        else:
            owners = [project]
        for owner in owners:
            if module == 'translation':
                rows=rates.order_rates(db,owner,owner.language_pair or project.language_pair)
                number_=numbers[str(owner.id)]
            else:
                _, _, rows, version, number_ = project_state(module, db, project.id, owner.id)
            if not rows: continue  # 尚无项目单价时使用自动带出的客户参考价。
            expected = matching(module, project, owner, rows, refs)
            if signature(module, rows) == signature(module, expected): continue
            result.append(dict(project_id=str(project.id), order_id=str(owner.id), order_no=number_, project_name=getattr(owner,'sub_project_name',None) or project.project_name,
                project_rates=rows, customer_rates=expected, version=version, customer_version=customer_version))
    return dict(ready=True, items=result[(page-1)*10:page*10], total=len(result))


class SyncWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    order_id: UUID
    version: str
    customer_version: str
    direction: Literal['project_to_client','client_to_project']
    confirmed: bool = False


@router.post('/{module}/{client_id}/sync')
def sync(module: Literal['translation','interpretation'], client_id: UUID, data: SyncWrite,
         db=Depends(get_db), user=Depends(get_current_user)):
    if not data.confirmed: raise HTTPException(422, '请点击并确认同步单价')
    require(db, user, 'clients:write' if data.direction == 'project_to_client' else 'projects:write')
    if data.direction == 'client_to_project':require(db, user, 'clients:read')
    try:
        if not db.query(Client).filter_by(id=client_id).with_for_update().first(): raise HTTPException(404, '客户不存在')
        from interpretation_models import InterpretationProject
        model = TranslationProject if module == 'translation' else InterpretationProject
        db.query(model).filter_by(id=data.project_id).with_for_update().populate_existing().first()
        refs, customer_version, available = library(module, db, client_id)
        project, owner, rows, version, _ = project_state(module, db, data.project_id, data.order_id)
        if project.client_id != client_id: raise HTTPException(422, '项目不属于当前客户')
        if not available: raise HTTPException(503, '财务存储尚未初始化')
        if version != data.version or customer_version != data.customer_version:
            raise HTTPException(409, '客户或项目单价已变化，请刷新差异后重新确认')
        if data.direction == 'project_to_client':
            if not rows: raise HTTPException(422, '项目尚未登记单价')
            if module == 'translation':
                import customer_translation_rates as rates
                rates.write_library(db,user,client_id,[rates.RateInput(**row) for row in rows],customer_version,origin='project',merge=True)
                db.commit()
            else:
                import interpretation_customer_finance as oral
                client = oral.record(db,'client',client_id)
                payload = deepcopy(client.payload) if client else oral.FinanceWrite(revision=0).model_dump(mode='json',exclude={'revision','update_library','library_revision','sync_confirmed'})
                merged = {oral_key(row): row for row in refs}
                for row in rows:
                    key = oral_key(row)
                    if sum(oral_key(item)==key for item in rows)>1: raise HTTPException(422,'同方向及单位存在多条单价，请先整理项目价格')
                    merged[key] = dict(row,quantity='1')
                if len(merged)>100: raise HTTPException(422,'客户参考价不能超过100条')
                payload['rates'] = list(merged.values())
                oral.save(db,user,'client',client_id,oral.FinanceWrite(revision=int(customer_version),**payload))
        elif module == 'translation':
            import customer_translation_rates as rates
            import translation_customer_finance as finance
            values = matching(module,project,owner,rows,refs)
            if not values: raise HTTPException(422,'客户尚未登记匹配方向的单价')
            current = finance.tree(project)['item']
            def find(node):
                if node['id']==str(owner.id): return node
                return next((found for child in node['children'] if (found:=find(child))),None)
            selected=find(current)
            allowed=set(rates.RateInput.model_fields)
            finance.save(db,user,project.id,finance.PriceWrite(version=version,order_id=owner.id,
                prices=[rates.RateInput(**{k:v for k,v in row.items() if k in allowed}) for row in values],
                adjusted_total=selected['adjusted_total'],explanation=selected['explanation'],billing_month=selected['billing_month']))
        else:
            import interpretation_customer_finance as oral
            existing = oral.record(db,'project',project.id)
            payload = deepcopy(existing.payload) if existing else oral.context(db,'project',project.id)['payload']
            defaults = matching(module,project,owner,rows,refs)
            if not defaults: raise HTTPException(422,'客户尚未登记匹配方向的单价')
            quantities = {oral_key(row): row['quantity'] for row in rows}
            payload['rates'] = [dict(row,quantity=quantities.get(oral_key(row),'1')) for row in defaults]
            oral.save(db,user,'project',project.id,oral.FinanceWrite(revision=int(version),**payload))
        return dict(success=True)
    except Exception:
        db.rollback()
        raise
