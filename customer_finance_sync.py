"""客户参考价同步与各业务模块的价格差异处理。"""
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


def has_registered_unit_price(row):
    tax = row.get('tax_prices') or {}
    return any(value is not None and value != '' for value in (
        row.get('amount'), tax.get('unit_price_excl_tax'), tax.get('unit_price_incl_tax'),
    ))


def oral_key(row):
    return (row['direction'], row['currency'], row['unit'],
            number(row.get('hours')) if row['unit'] in ('天', '半天') else None,
            bool(row.get('includes_lunch')) if row['unit'] == '天' else False)


def tax_signature(row):
    value=row.get('tax_prices') or {}
    result=tuple(number(value.get(field)) for field in ('unit_price_excl_tax','unit_price_incl_tax'))
    return (None,None) if result[1] is None and result[0] == number(row.get('amount')) else result


def reference_tax(row):
    value=row.get('tax_prices')
    return None if value is None else {key:(None if key.startswith('total_') else amount) for key,amount in value.items()}


def signature(module, rows):
    import customer_translation_rates as rates
    key = rates.rate_key if module == 'translation' else oral_key
    # 数量为项目自身的业务量，不属于客户单价，重复组合项也保留以识别歧义。
    return sorted([(str(key(row)), number(row['amount']),tax_signature(row)) for row in rows], key=str)


def translation_basis_matches(reference, price, matrix):
    from translation_rate_matching import matches
    from translation_quantity_basis import resolve

    return (resolve({}, reference['metric'])[1] == resolve(matrix, price['metric'])[1]
            and matches(reference, price, right_matrix=matrix, left_reference=True))

def translation_rates_agree(rows, references, matrix):
    remaining = list(references)
    for row in rows:
        def agrees(reference):
            return (translation_basis_matches(reference, row, matrix)
                    and number(reference['amount']) == number(row['amount'])
                    and tax_signature(reference) == tax_signature(row))

        index = next((index for index, reference in enumerate(remaining) if agrees(reference)), None)
        if index is None:
            return False
        remaining.pop(index)

    automatic_directions = {row['language_pair'].casefold() for row in rows if row['metric'] == 'customer_auto'}
    return all(reference['language_pair'].casefold() in automatic_directions for reference in remaining)


def with_resolved_quantity_basis(rows, matrix):
    from translation_quantity_basis import resolve

    result = []
    for row in rows:
        if row['metric'] == 'customer_auto':
            _, dimension, metric, _ = resolve(matrix, row['metric'])
            row = dict(row, quantity_dimension=dimension, quantity_metric=metric)
        result.append(row)
    return result


def oral_defaults(project, rows):
    directions = {' ↔ '.join(item.language_labels) for item in project.language_directions}
    return [{**deepcopy(row), 'quantity': '1'} for row in rows if row['direction'] in directions]


def translation_defaults(owner, project, rows):
    from translation_rate_matching import references_for_new_prices
    return [dict(row, id=None, reference_id=row['id'], reference_revision=row['revision'])
            for row in references_for_new_prices(rows, owner.language_pair or project.language_pair, owner.word_count_matrix)]


def auto_translation(db, user, client_id, before, after, project_id=None, *, changed_only=False, sub_client_id=None, overwrite=False):
    import customer_translation_rates as rates
    import translation_customer_finance as finance
    import translation_finance_audit as audit
    import translation_quantity_basis as quantity_basis
    if not before and not after:return
    audit.require_ready(db)
    from translation_rate_matching import automatic_reference, matches
    previous_ids={row['id']:row for row in before};current_ids={row['id']:row for row in after}
    changed_refs = [row for row in after if row['id'] not in previous_ids or
                    number(row['amount'])!=number(previous_ids[row['id']]['amount']) or
                    tax_signature(row)!=tax_signature(previous_ids[row['id']])]
    changed_ids={row['id'] for row in changed_refs}
    if changed_only and not changed_refs:
        return
    from models import SubClient
    from sqlalchemy import func
    parent_refs = {row['id']: row for row in rates.library(db, client_id)['items']} if sub_client_id else {}
    query = db.query(TranslationProject).outerjoin(SubClient,SubClient.id==TranslationProject.sub_client_id).filter(
        func.coalesce(TranslationProject.client_id,SubClient.parent_client_id)==client_id,
        TranslationProject.annotation_migrated_at.is_(None))
    if sub_client_id:
        query = query.filter(TranslationProject.sub_client_id == sub_client_id)
    if project_id:
        query = query.filter(TranslationProject.id == project_id)
    projects = query.order_by(TranslationProject.id).with_for_update(of=TranslationProject).all()
    child_refs_by_id = {
        child_id: rates.library(db, client_id, child_id)['items']
        for child_id in {project.sub_client_id for project in projects if project.sub_client_id}
    } if not sub_client_id else {}
    for project in projects:
        project = finance.crud.get_translation_project(db,project.id)
        child_refs = child_refs_by_id.get(project.sub_client_id, [])
        defaults = rates.project_rate_defaults(after, child_refs)
        competing_ids = {row['id'] for row in child_refs}
        finance.crud._attach_word_count_matrices(db,projects=[project])
        captured = audit.capture(project)
        changed_orders = []
        owners, numbers, parents = finance.hierarchy(project)
        modes = finance.order_pricing_modes(db, project)
        for owner in owners:
            if modes.get(str(owner.id))=='aggregate' or finance.inherits_fixed_pricing(project,parents,str(owner.id)):
                continue
            if str(owner.id) in getattr(project,'cleared_price_orders',()):continue
            if any(charge.pricing_mode=='fixed' for charge in owner.customer_charge_items):continue
            rows = rates.order_rates(db, owner, owner.language_pair or project.language_pair)
            candidates = rows or translation_defaults(owner, project, defaults)
            by_id = {str(row.id): row for row in owner.customer_charge_items}
            changed = False
            for data in candidates:
                reference_id = data.get('reference_id')
                if overwrite:
                    ref = automatic_reference(defaults,data,owner.word_count_matrix)
                    if not ref:
                        linked = current_ids.get(reference_id)
                        if linked and matches(linked,data,right_matrix=owner.word_count_matrix,left_reference=True):
                            ref = linked
                elif not rows:
                    ref=current_ids.get(reference_id)
                elif reference_id:
                    linked=current_ids.get(reference_id)
                    old=previous_ids.get(reference_id) or parent_refs.get(reference_id)
                    if not old or number(data['amount'])!=number(old['amount']) or tax_signature(data)!=tax_signature(old):
                        continue
                    if linked:
                        ref=linked if matches(linked,data,right_matrix=owner.word_count_matrix,left_reference=True) else None
                    elif reference_id in parent_refs:
                        ref=automatic_reference(after,data,owner.word_count_matrix)
                    else:
                        continue
                else:
                    ref=automatic_reference(defaults,data,owner.word_count_matrix)
                    if data['amount'] is not None:
                        old = automatic_reference(before,data,owner.word_count_matrix)
                        if old or not ref or number(data['amount']) != number(ref['amount']) or tax_signature(data) != tax_signature(ref):
                            continue
                if ref and ref['id'] in competing_ids:
                    continue
                if not ref or (changed_only and ref['id'] not in changed_ids):
                    continue
                charge = by_id.get(data.get('id'))
                moment = business_now().replace(tzinfo=None)
                if charge is None:
                    charge = TranslationSubOrderChargeItem(id=uuid4(), translation_project_id=project.id if owner is project else None,
                        sub_order_id=None if owner is project else owner.id, sequence_no=max((item.sequence_no or 0 for item in owner.customer_charge_items),default=0)+1,
                        item_name='翻译费', pricing_mode='metric', created_at=moment)
                    owner.customer_charge_items.append(charge)
                elif reference_id == ref['id'] and number(data['amount']) == number(ref['amount']) and tax_signature(data)==tax_signature(ref) and data.get('reference_revision') == ref['revision']:
                    continue
                tax=ref.get('tax_prices')
                charge.unit_price_excl_tax=Decimal(tax['unit_price_excl_tax']) if tax and tax.get('unit_price_excl_tax') is not None else (None if tax else Decimal(ref['amount']))
                charge.unit_price_incl_tax=Decimal(tax['unit_price_incl_tax']) if tax and tax.get('unit_price_incl_tax') is not None else None
                charge.unit_price=charge.unit_price_excl_tax if charge.unit_price_incl_tax is not None else Decimal(ref['amount'])
                charge.currency = ref['currency']; charge.metric_type = quantity_basis.storage_metric(quantity_basis.resolve(owner.word_count_matrix,ref['metric'])[2]); charge.unit_size = Decimal(ref['unit_size'])
                charge.updated_at = moment; owner.updated_at = moment; project.updated_at = moment
                db.flush()
                quantity_basis.store(db,charge,data['metric'] if rows else ref['metric'],owner.word_count_matrix)
                meta = db.get(rates.TranslationChargeDirection, charge.id)
                if meta is None:
                    meta = rates.TranslationChargeDirection(charge_id=charge.id); db.add(meta)
                meta.language_pair = ref['language_pair']; meta.reference_id = UUID(ref['id']); meta.reference_revision = ref['revision']
                changed = True
            if changed:
                changed_orders.append((owner, rows))
        if changed_orders:
            db.flush(); rates.invalidate_metadata(db); quantity_basis.invalidate(db)
            if sub_client_id:
                for owner, before_rates in changed_orders:
                    rates.record_library_history(
                        db, user, client_id, sub_client_id, before_rates,
                        rates.order_rates(db, owner, owner.language_pair or project.language_pair),
                        'automatic_order_sync', project_id=project.id, order_id=owner.id,
                        order_no=numbers[str(owner.id)],
                    )
            finance.confirmations.recheck_after_fee_change(db,project.id,user.id)
            audit.append(db, user, project, captured)


def inherit_translation(db, project, user_id):
    import customer_translation_rates as rates
    import translation_finance_audit as audit
    from models import AppUser
    client_id = project.client_id or (project.sub_client.parent_client_id if project.sub_client else None)
    if not client_id or not user_id or not rates.ready(db) or not audit.ready(db): return
    user=db.get(AppUser,user_id)
    if not user:
        return
    child = rates.library(db,client_id,project.sub_client_id)['items'] if project.sub_client_id else []
    if child:
        auto_translation(db,user,client_id,[],child,project.id,sub_client_id=project.sub_client_id)
    refs=rates.library(db,client_id)['items']
    if refs:
        auto_translation(db,user,client_id,[],refs,project.id)


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
        if oral.settlement(payload).pricing_mode == 'fixed':
            continue
        original = deepcopy(payload)
        if not payload.get('rates'):
            payload['rates'] = oral_defaults(project, after)
        else:
            for item in payload['rates']:
                key = oral_key(item)
                if key in previous and key in current and number(item['amount']) == number(previous[key]['amount']) and tax_signature(item)==tax_signature(previous[key]):
                    item['amount'] = current[key]['amount']
                    item['tax_prices'] = reference_tax(current[key])
        if payload != original:
            store_oral(db, user, 'project', project.id, payload, row)


def require(db, user, code):
    if not user_has_permission(db, user.id, code) and not (code.endswith(':read') and user_has_permission(db,user.id,code.replace(':read',':write'))):
        raise HTTPException(403, '无权执行此单价同步操作')


def library(module, db, client_id, sub_client_id=None):
    if module == 'translation':
        import customer_translation_rates as rates
        result = rates.library(db, client_id, sub_client_id)
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
    rates = row.payload.get('rates', []) if row and oral.settlement(row.payload).pricing_mode != 'fixed' else []
    return project, project, deepcopy(rates), str(row.revision if row else 0), project.order_no


def matching(module, project, owner, rows, references):
    if module == 'translation':
        matched = [ref for ref in references if any(
            translation_basis_matches(ref, row, owner.word_count_matrix) for row in rows
        )]
        directions = {ref['language_pair'] for ref in matched}
        return [*(dict(row, id=None, reference_id=row['id'], reference_revision=row['revision']) for row in matched),
                *(row for row in translation_defaults(owner, project, references) if row['language_pair'] not in directions)]
    return oral_defaults(project, references)


router = APIRouter(prefix='/customer-finance-sync', tags=['customer-finance-sync'])


def translation_difference_tree(owners, numbers, parents, directions, differences):
    children = {}
    for order_id, parent_id in parents.items():
        children.setdefault(parent_id, []).append(order_id)
    by_id = {str(owner.id): owner for owner in owners}
    by_order = {row['order_id']: row for row in differences}

    def build(order_id):
        owner = by_id[order_id]
        subtree_directions = set(directions[order_id])
        branches = []
        for child_id in children.get(order_id, []):
            child, child_directions = build(child_id)
            subtree_directions.update(child_directions)
            if child:
                branches.append((child, child_directions))

        own_difference = by_order.get(order_id)
        if not own_difference and not branches:
            return None, subtree_directions
        node = own_difference or dict(
            order_id=order_id, order_no=numbers[order_id],
            project_name=getattr(owner, 'sub_project_name', None) or owners[0].project_name,
        )
        node = {**node, 'language_directions': sorted(subtree_directions - {''})}
        if not branches:
            return node, subtree_directions
        if len(subtree_directions) == 1 and '' not in subtree_directions:
            node['children'] = [child for child, _ in branches]
            return node, subtree_directions

        # Group only siblings whose entire branch uses the same known direction.
        groups = {}
        for child, child_directions in branches:
            if len(child_directions) == 1 and '' not in child_directions:
                groups.setdefault(next(iter(child_directions)), []).append(child)
        node['children'] = []
        node['expand_by_default'] = True
        shown = set()
        for child, child_directions in branches:
            direction = next(iter(child_directions)) if len(child_directions) == 1 else None
            siblings = groups.get(direction, [])
            if len(siblings) < 2:
                node['children'].append(child)
            elif direction not in shown:
                shown.add(direction)
                node['children'].append(dict(
                    order_id=f'{order_id}:direction:{direction}', direction_group=True,
                    language_directions=[direction], children=siblings,
                ))
        return node, subtree_directions

    return build(str(owners[0].id))[0]


@router.get('/{module}/{client_id}/differences')
def differences(module: Literal['translation','interpretation','annotation'], client_id: UUID,
                page: int = Query(1, ge=1), db=Depends(get_db), user=Depends(get_current_user),
                group_orders: bool = False, sub_client_id: UUID | None = None):
    if module == 'annotation':
        from customer_annotation_rate_sync import differences as annotation_differences
        return annotation_differences(db, user, client_id, page)
    require(db, user, 'clients:read' if user_has_permission(db, user.id, 'clients:read') else 'clients:write')
    refs, customer_version, available = library(module, db, client_id, sub_client_id)
    if not available: return dict(ready=False, items=[], total=0)
    from interpretation_models import InterpretationProject
    model = TranslationProject if module == 'translation' else InterpretationProject
    query = db.query(model).filter_by(client_id=client_id)
    if module == 'translation':
        if sub_client_id:
            query = db.query(model).filter_by(sub_client_id=sub_client_id)
        else:
            query = query.filter(model.sub_client_id.is_(None))
        query = query.filter(model.annotation_migrated_at.is_(None))
    result = []
    grouped = module == 'translation' and group_orders
    difference_count = 0
    for project in query.order_by(model.id).all():
        if module == 'translation':
            import translation_customer_finance as finance
            import customer_translation_rates as rates
            project=finance.crud.get_translation_project(db,project.id)
            owners,numbers,parents = finance.hierarchy(project)
            version=finance.version(project)
        else:
            owners = [project]
        project_differences = []
        directions = {}
        for owner in owners:
            if module == 'translation':
                rows=rates.order_rates(db,owner,owner.language_pair or project.language_pair)
                number_=numbers[str(owner.id)]
                if grouped:
                    owner_direction = owner.language_pair or project.language_pair or ''
                    directions[str(owner.id)] = {
                        value.strip() for value in owner_direction.split('；') if value.strip()
                    } | {row['language_pair'] for row in rows if row.get('language_pair')}
                    if not directions[str(owner.id)]:
                        directions[str(owner.id)].add('')
            else:
                _, _, rows, version, number_ = project_state(module, db, project.id, owner.id)
            if module == 'translation':
                rows = [row for row in rows if has_registered_unit_price(row)]
            if not rows: continue  # 尚无项目单价时使用自动带出的客户参考价。
            expected = matching(module, project, owner, rows, refs)
            if module == 'translation':
                expected = [reference for reference in expected if any(
                    translation_basis_matches(reference, row, owner.word_count_matrix) for row in rows
                )]
                if translation_rates_agree(rows, expected, owner.word_count_matrix): continue
                rows = with_resolved_quantity_basis(rows, owner.word_count_matrix)
            elif signature(module, rows) == signature(module, expected): continue
            project_differences.append(dict(project_id=str(project.id), order_id=str(owner.id), order_no=number_, project_name=getattr(owner,'sub_project_name',None) or project.project_name,
                project_rates=rows, customer_rates=expected, version=version, customer_version=customer_version))
        if grouped:
            if project_differences:
                difference_count += len(project_differences)
                result.append(translation_difference_tree(owners, numbers, parents, directions, project_differences))
        else:
            result.extend(project_differences)
    if grouped:
        return dict(ready=True, items=result[(page-1)*10:page*10], total=len(result), difference_count=difference_count)
    return dict(ready=True, items=result[(page-1)*10:page*10], total=len(result))


class SyncWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: UUID
    order_id: UUID
    version: str
    customer_version: str
    direction: Literal['project_to_client','client_to_project']
    confirmed: bool = False
    sub_client_id: UUID | None = None


@router.post('/{module}/{client_id}/sync')
def sync(module: Literal['translation','interpretation','annotation'], client_id: UUID, data: SyncWrite,
         db=Depends(get_db), user=Depends(get_current_user)):
    if module == 'annotation':
        from customer_annotation_rate_sync import synchronize
        return synchronize(db, user, client_id, data)
    if not data.confirmed: raise HTTPException(422, '请点击并确认同步单价')
    require(db, user, 'clients:write' if data.direction == 'project_to_client' else 'projects:write')
    if data.direction == 'client_to_project':require(db, user, 'clients:read')
    try:
        if not db.query(Client).filter_by(id=client_id).with_for_update().first(): raise HTTPException(404, '客户不存在')
        from interpretation_models import InterpretationProject
        model = TranslationProject if module == 'translation' else InterpretationProject
        db.query(model).filter_by(id=data.project_id).with_for_update().populate_existing().first()
        project, owner, rows, version, order_no = project_state(module, db, data.project_id, data.order_id)
        parent_id = project.client_id or (project.sub_client.parent_client_id if module == 'translation' and project.sub_client else None)
        sub_client_id = data.sub_client_id
        if module == 'translation' and data.direction == 'project_to_client' and 'sub_client_id' not in data.model_fields_set:
            sub_client_id = project.sub_client_id
        if parent_id != client_id or sub_client_id and (module != 'translation' or project.sub_client_id != sub_client_id):
            raise HTTPException(422, '项目不属于当前客户或子客户')
        refs, customer_version, available = library(module, db, client_id, sub_client_id)
        if not available: raise HTTPException(503, '财务存储尚未初始化')
        if version != data.version or customer_version != data.customer_version:
            raise HTTPException(409, '客户或项目单价已变化，请刷新差异后重新确认')
        if data.direction == 'project_to_client':
            if not rows: raise HTTPException(422, '项目尚未登记单价')
            if module == 'translation':
                import customer_translation_rates as rates
                from translation_quantity_basis import resolve
                values = []
                for row in rows:
                    if row['amount'] is None:
                        continue
                    _, dimension, metric, _ = resolve(owner.word_count_matrix, row['metric'])
                    if not metric: raise HTTPException(422, '同步客户报价前，请先明确项目计量单位')
                    candidates = [ref for ref in refs if translation_basis_matches(ref, row, owner.word_count_matrix)]
                    if len(candidates)>1: raise HTTPException(422, '客户报价存在多条完整匹配项，请先编辑客户报价消除重复')
                    if candidates:
                        row = dict(row, metric=candidates[0]['metric'])
                    elif row['metric'] == 'customer_auto':
                        row = dict(row, metric=f'company_{metric}' if dimension == 'company' else f'customer_auto:{metric}')
                    values.append(rates.RateInput(**row))
                if not values:
                    raise HTTPException(422, '项目尚未填写有效单价')
                rates.write_library(db,user,client_id,values,customer_version,origin='project',merge=True,
                                    sub_client_id=sub_client_id, project_id=project.id, order_id=owner.id, order_no=order_no)
                db.commit()
            else:
                import interpretation_customer_finance as oral
                client = oral.record(db,'client',client_id)
                payload = deepcopy(client.payload) if client else oral.FinanceWrite(revision=0).model_dump(mode='json',exclude={'revision','update_library','library_revision','sync_confirmed'})
                merged = {oral_key(row): row for row in refs}
                for row in rows:
                    key = oral_key(row)
                    if sum(oral_key(item)==key for item in rows)>1: raise HTTPException(422,'同方向及单位存在多条单价，请先整理项目价格')
                    merged[key] = dict(row,quantity='1',tax_prices=reference_tax(row))
                if len(merged)>100: raise HTTPException(422,'客户参考价不能超过100条')
                payload['rates'] = list(merged.values())
                oral.save(db,user,'client',client_id,oral.FinanceWrite(revision=int(customer_version),**payload))
        elif module == 'translation':
            import customer_translation_rates as rates
            import translation_customer_finance as finance
            from translation_rate_matching import automatic_reference
            values = matching(module,project,owner,rows,refs)
            current = finance.tree(project)['item']
            def find(node):
                if node['id']==str(owner.id): return node
                return next((found for child in node['children'] if (found:=find(child))),None)
            selected=find(current)
            if selected['pricing_mode'] == 'fixed' or selected.get('price_aggregate') or selected.get('fixed_pricing_from'):
                raise HTTPException(422, '请在按工作量计价的订单中同步单价')
            if rows:
                updated = []
                changed = False
                for row in rows:
                    reference = automatic_reference(refs, row, owner.word_count_matrix)
                    if reference:
                        tax = reference_tax(reference) or {'unit_price_excl_tax': reference['amount']}
                        tax.update({key: amount for key, amount in row['tax_prices'].items() if key.startswith('total_')})
                        row = dict(row, amount=reference['amount'], tax_prices=tax,
                                   reference_id=reference['id'], reference_revision=reference['revision'])
                        changed = True
                    if row['amount'] is not None:
                        updated.append(row)
                if not changed:
                    raise HTTPException(422, '没有语种、单位、币种及计价数量均匹配的参考价')
                values = updated
            if not values:
                raise HTTPException(422, '客户尚未登记匹配方向的单价')
            allowed=set(rates.RateInput.model_fields)
            payload = finance.PriceWrite(version=version,order_id=owner.id,
                prices=[rates.RateInput(**{k:v for k,v in row.items() if k in allowed}) for row in values],
                adjusted_total=selected['adjusted_total'],adjusted_total_incl_tax=selected['adjusted_total_incl_tax'],
                explanation=selected['explanation'],billing_month=selected['billing_month'])
            if sub_client_id:
                finance._write_finance(db, user, project.id, payload)
                rates.invalidate_metadata(db)
                after = rates.order_rates(db, owner, owner.language_pair or project.language_pair)
                rates.record_library_history(
                    db, user, client_id, sub_client_id, rows, after, 'manual_order_sync',
                    project_id=project.id, order_id=owner.id, order_no=order_no,
                )
                db.commit()
            else:
                finance.save(db, user, project.id, payload)
        else:
            import interpretation_customer_finance as oral
            existing = oral.record(db,'project',project.id)
            payload = deepcopy(existing.payload) if existing else oral.context(db,'project',project.id)['payload']
            payload.pop('quotation', None)
            payload.pop('invoice', None)
            defaults = matching(module,project,owner,rows,refs)
            if not defaults: raise HTTPException(422,'客户尚未登记匹配方向的单价')
            quantities = {oral_key(row): row['quantity'] for row in rows}
            payload['rates'] = [dict(row,quantity=quantities.get(oral_key(row),'1')) for row in defaults]
            oral.save(db,user,'project',project.id,oral.FinanceWrite(revision=int(version),**payload))
        return dict(success=True)
    except Exception:
        db.rollback()
        raise
