"""正常提交的子订单资料检查，以及明确标识的紧急项目预告知。"""
from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Uuid, inspect
from sqlalchemy.orm import Mapped, mapped_column
from models import Base, TranslationProject, TranslationSubOrder


class TranslationProjectSubmission(Base):
    __tablename__ = 'translation_project_submission'
    project_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('translation_project.id', ondelete='CASCADE'), primary_key=True)
    emergency_notice: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sub_orders_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


def ready(db):
    return inspect(db.connection()).has_table(TranslationProjectSubmission.__tablename__)


def missing_statistics(db, root):
    from word_count_service import hierarchy_matrix
    hierarchy_matrix(db, 'project', root)
    rows=db.query(TranslationSubOrder).filter_by(parent_project_id=root.id).all()
    parents={row.sub_order_no.rsplit('.',1)[0] for row in rows}
    return [row.sub_order_no for row in rows if row.sub_order_no not in parents and not any(
        value is not None for dimension in ('company','customer')
        for value in (row.word_count_matrix.get(dimension,{}) or {}).values())]


def validate_initial_details(details):
    from fastapi import HTTPException
    from pydantic import ValidationError
    from schemas import TranslationSubOrderUpdate
    allowed=set(TranslationSubOrderUpdate.model_fields)-{'inherit_fields','assigned_translator_completions'}
    result={}
    for suffix,data in details.items():
        if set(data)-allowed:
            raise ValueError('子订单预填内容与生成的订单不匹配，请重新打开子订单管理')
        try:
            result[suffix]=TranslationSubOrderUpdate.model_validate(data)
        except ValidationError as exc:
            errors=exc.errors(include_url=False,include_context=False,include_input=False)
            for error in errors:
                error['loc']=['body','initial_sub_order_details',suffix,*error['loc']]
            raise HTTPException(status_code=422,detail=errors) from exc
    return result


def apply_initial_details(db, root, details, *, split_imported_files=False):
    if not details and not split_imported_files:
        return 0
    from translation_order_inheritance import prepare
    from crud import update_sub_order
    from translation_direction_service import directions
    from translation_folder_orders import info
    from schemas import TranslationSubOrderUpdate

    context=prepare(db,root.id)
    by_suffix={row.sub_order_no[len(root.order_no)+1:]:row for row in context[1]}
    payloads = validate_initial_details(details)
    suffixes = payloads.keys() | by_suffix.keys() if split_imported_files else payloads.keys()
    created_count = 0
    # 上级先保存，方向拆出的子单才能接收各自的预填资料。
    for suffix in sorted(suffixes):
        if suffix not in by_suffix:
            raise ValueError('子订单预填内容与生成的订单不匹配，请重新打开子订单管理')
        row = by_suffix[suffix]
        payload = payloads.get(suffix)
        if (split_imported_files and (payload is None or 'language_pair' not in payload.model_fields_set)
                and len(directions(row.language_pair)) > 1 and not info(db, row.id)):
            values = payload.model_dump(exclude_unset=True) if payload else {}
            payload = TranslationSubOrderUpdate(language_pair=row.language_pair, **values)
        if payload is None:
            continue
        updated = update_sub_order(db, row.id, payload, commit=False)
        if count := updated.auto_created_child_count:
            created_count += count
            for child in db.query(TranslationSubOrder).filter_by(parent_project_id=root.id):
                by_suffix[child.sub_order_no[len(root.order_no)+1:]] = child
    return created_count


def apply(db, root, mode, reviewed=False):
    if mode is None:
        return
    if not ready(db):
        raise ValueError('项目提交检查表尚未初始化，请联系管理员')
    has_children=db.query(TranslationSubOrder.id).filter_by(parent_project_id=root.id).first() is not None
    if mode=='normal_children' and not has_children:
        raise ValueError('请先创建子订单并填写字数，汇总至母订单后再发送')
    if mode in ('normal','normal_children') and has_children:
        if not reviewed:
            raise ValueError('请先打开子订单管理，填写并确认子订单统计后再保存；紧急情况可使用“（紧急）项目预告知”')
        missing=missing_statistics(db,root)
        if missing:
            raise ValueError('请先填写子订单的我司统计或客户统计：'+'、'.join(missing[:10])+('等' if len(missing)>10 else ''))
    row=db.get(TranslationProjectSubmission,root.id)
    if row is None:
        row=TranslationProjectSubmission(project_id=root.id)
        db.add(row)
    row.emergency_notice=mode=='emergency_notice'
    row.sub_orders_reviewed=bool(reviewed) and mode!='draft'
    db.flush()


def mail_policy(db, root):
    if not ready(db):
        return False, ''
    state=db.get(TranslationProjectSubmission,root.id)
    if state and state.emergency_notice:
        return True, ''
    if state and not state.sub_orders_reviewed:
        return False, '请先在子订单管理填写字数并汇总至母订单，再保存并发送；紧急情况可使用“（紧急）项目预告知”'
    # 已有历史发送规则不在迁移时批量改写；所有带子订单邮件均检查实际资料。
    if db.query(TranslationSubOrder.id).filter_by(parent_project_id=root.id).first():
        if not state or not state.sub_orders_reviewed:
            return False, '请先在子订单管理填写并确认资料，再保存项目；紧急情况可使用“（紧急）项目预告知”'
        missing=missing_statistics(db,root)
        if missing:
            return False, '子订单缺少我司统计或客户统计：'+'、'.join(missing[:10])
    return False, ''
