"""日报同项目的二级工作项，关系保存在现有 JSON 元数据中。"""
def normalize_hierarchy(items):
    by_key={str(item['display_metadata']['_feedback_key']):item for item in items}
    roots={}
    for item in items:
        metadata=item['display_metadata']
        parent_key=metadata.get('parent_item_key')
        if parent_key:
            parent=by_key.get(str(parent_key))
            if parent is None or parent is item:
                raise ValueError('工作报告下级关系无效，请刷新后重试')
        elif item.get('source_type')!='system_event':
            order=str(metadata.get('order_no') or '').strip().casefold()
            if order and order in roots:
                metadata['parent_item_key']=roots[order]
            elif order:
                roots[order]=str(metadata['_feedback_key'])
    # 对齐父级身份信息，防止客户端伪造同一项目的类型和名称。
    for item in items:
        metadata=item['display_metadata'];parent_key=metadata.get('parent_item_key')
        if not parent_key:continue
        parent=by_key[str(parent_key)];source=parent['display_metadata'];seen={str(metadata['_feedback_key'])}
        while source.get('parent_item_key'):
            key=str(source['_feedback_key'])
            if key in seen:raise ValueError('工作报告下级关系不能循环')
            seen.add(key)
            parent=by_key.get(str(source['parent_item_key']))
            if parent is None:raise ValueError('工作报告上级不存在')
            source=parent['display_metadata']
        metadata['parent_item_key']=source['_feedback_key']
        item['task_type']=parent['task_type'];item['task_name']=parent['task_name']
        metadata['order_no']=source.get('order_no','')
        for key in ['report_types','custom_project_type']:
            if key in source:metadata[key]=source[key]
            elif key!='report_types':metadata.pop(key,None)
    result=[]
    for item in items:
        if item['display_metadata'].get('parent_item_key'):continue
        result.append(item)
        key=item['display_metadata']['_feedback_key']
        result.extend(child for child in items if child['display_metadata'].get('parent_item_key')==key)
    return result


def outline_numbers(items):
    roots={};counts={};result=[]
    for item in items:
        metadata=item.display_metadata or {}
        if not metadata.get('parent_item_key'):
            roots[str(metadata.get('_feedback_key') or item.id)]=len(roots)+1
    for index,item in enumerate(items,1):
        metadata=item.display_metadata or {};parent=str(metadata.get('parent_item_key') or '')
        if parent in roots:
            counts[parent]=counts.get(parent,0)+1;result.append(f'{roots[parent]}.{counts[parent]}')
        else:result.append(str(roots.get(str(metadata.get('_feedback_key') or item.id),index)))
    return result
