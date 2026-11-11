"""按翻译方向补齐文件子订单，沿用点号层级、现有事务和编号池。"""
import re
from sqlalchemy import select
from models import TranslationProject,TranslationSubOrder
from language_catalog import normalize_language_pairs
from translation_file_name_rules import normalize_single_file_name


def directions(value):
    return [item for item in (normalize_language_pairs(value) or '').split('；') if item]


def level(row):
    return row.sub_order_no.count('.') if isinstance(row,TranslationSubOrder) else 0


def preserves_order_statistics(owner, children):
    """同一文件按方向拆单时，上级保留原文统计。"""
    if not children or getattr(owner, 'folder_info', None):
        return False
    wanted = {pair.casefold() for pair in directions(owner.language_pair)}
    if len(wanted) < 2:
        return False
    if isinstance(owner, TranslationSubOrder):
        name = owner.sub_project_name
    else:
        name = owner.source_file_name or owner.project_name
    name = str(name or '').strip().casefold()
    return bool(name) and all(
        (str(child.sub_project_name or '').strip().casefold() == name or child.network_file_path == '同上一级订单')
        and len(pairs := directions(child.language_pair)) == 1 and pairs[0].casefold() in wanted
        for child in children
    )


def validate_direction_level(number,value):
    if str(number).count('.') >= 5 and len(directions(value)) > 1:
        raise ValueError('第五级为方向子订单，只能选择一个翻译方向')


def stored_matrix(db,owner):
    """复制原文件本身的统计，不能把父级已汇总的多方向工作量重复复制。"""
    from word_count_models import WordCountMetric
    from word_count_schemas import WordCountCreateMatrix
    import preliminary_word_count as preliminary
    import translation_duration_metrics as duration
    matrix=WordCountCreateMatrix().model_dump()
    child=isinstance(owner,TranslationSubOrder)
    rows=db.query(WordCountMetric).filter((WordCountMetric.sub_order_id if child else WordCountMetric.project_id)==owner.id).all()
    rows+=preliminary.rows(db,[] if child else [owner.id],[owner.id] if child else [])
    rows+=duration.rows(db,[] if child else [owner.id],[owner.id] if child else [])
    for row in rows:
        if row.count_value is not None and row.dimension in matrix and row.metric_type in matrix[row.dimension]:
            matrix[row.dimension][row.metric_type]=float(row.count_value) if row.metric_type in ('minutes','hours') else int(row.count_value)
    if not child:
        from translation_simple_requirement_counts import without_additions
        matrix=without_additions(db,owner,matrix)
    return WordCountCreateMatrix.model_validate(matrix)


def next_number(db,root,owner):
    from business_numbering import allocate
    number=owner.sub_order_no if isinstance(owner,TranslationSubOrder) else root.order_no
    pattern=re.compile(re.escape(number)+r'\.(\d+)$')
    existing=db.execute(select(TranslationSubOrder.sub_order_no).where(TranslationSubOrder.parent_project_id==root.id,TranslationSubOrder.sub_order_no.startswith(number+'.',autoescape=True))).scalars()
    minimum=max([int(match[1]) for value in existing if (match:=pattern.fullmatch(value))],default=0)+1
    return allocate(db,f'translation_suborder:{owner.id}',number+'.',minimum)


def ensure_direction_children(db,owner,actor_id=None):
    wanted=directions(owner.language_pair)
    if len(wanted)<2:return []
    from translation_folder_orders import info
    if isinstance(owner,TranslationSubOrder) and info(db,owner.id):return []
    if isinstance(owner,TranslationProject):
        from translation_folder_orders import TranslationOrderFolder,is_folder_root,ready
        if is_folder_root(db,owner.id):return []
        if ready(db) and db.query(TranslationOrderFolder).join(TranslationSubOrder,TranslationSubOrder.id==TranslationOrderFolder.sub_order_id).filter(TranslationSubOrder.parent_project_id==owner.id).first():return []
    if isinstance(owner, TranslationSubOrder):
        validate_direction_level(owner.sub_order_no, owner.language_pair)
    root_id=owner.parent_project_id if isinstance(owner,TranslationSubOrder) else owner.id
    root=db.query(TranslationProject).filter_by(id=root_id).with_for_update().one()
    db.flush()
    parent_no=owner.sub_order_no if isinstance(owner,TranslationSubOrder) else root.order_no
    children=db.query(TranslationSubOrder).filter_by(parent_project_id=root_id).with_for_update().all()
    direct=[row for row in children if row.sub_order_no.rsplit('.',1)[0]==parent_no]
    created=[]
    # 已经按文件建立的一级子单继续在其下面按方向拆分，不额外复制一套母单方向子单。
    if level(owner)==0:
        for row in direct:
            if len(directions(row.language_pair))>1:
                created.extend(ensure_direction_children(db,row,actor_id))
    sources={}
    direction_only = preserves_order_statistics(owner, direct)
    if direct and not direction_only:
        for row in sorted(direct,key=lambda item:item.sub_order_no):
            name=normalize_single_file_name(row.sub_project_name)
            sources.setdefault(name.casefold(),(name,row))
    else:
        name=normalize_single_file_name(owner.sub_project_name if isinstance(owner,TranslationSubOrder) else owner.source_file_name or owner.project_name)
        sources[name.casefold()]=(name,owner)
    from crud import _create_sub_order_in_transaction
    from schemas import TranslationSubOrderCreate
    for key,(name,source) in sources.items():
        covered={direction.casefold() for row in direct if direction_only or str(row.sub_project_name or '').casefold()==key for direction in directions(row.language_pair)}
        for direction in wanted:
            if direction.casefold() in covered:
                continue
            number=next_number(db,root,owner)
            payload=TranslationSubOrderCreate(parent_project_id=root.id,sub_order_no=number,sub_project_name=name,language_pair=direction,
                priority=source.priority or owner.priority,file_type_secondary=source.file_type_secondary,
                customer_deadline_time=source.customer_deadline_time or getattr(owner,'customer_deadline_time',None),
                network_file_path='同上一级订单',word_count_matrix=stored_matrix(db,source),created_by=actor_id or getattr(owner,'created_by',None))
            child=_create_sub_order_in_transaction(db,payload, direction_child=True)
            created.append(child);covered.add(direction.casefold())
    if created:
        db.expire(root,['sub_orders'])
    return created
