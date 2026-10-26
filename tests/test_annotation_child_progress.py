"""只读跨层级进度提示，使用内存隔离库。"""
from uuid import uuid4
from test_chat_participant_access import environment,project


def test_three_tracks_unmirrored_and_grandchildren(environment):
    db,(owner,_,__)=environment
    from annotation_ops_models import AnnotationProjectStatusHistory as History
    from annotation_customer_progress_models import AnnotationCustomerProgress as Customer
    from annotation_annotator_progress_models import AnnotationAnnotatorProgress as Annotator
    from annotation_child_progress import attach_counts,listing
    from annotation_progress_time import business_now
    parent=project(db,owner,'AP-P');child=project(db,owner,'AP-P.001');grandchild=project(db,owner,'AP-P.001.001')
    child.parent_project_id=parent.id;grandchild.parent_project_id=child.id;db.flush()
    now=business_now()
    def add(model,order,note):
        values=dict(id=uuid4(),project_id=order.id,change_note=note,effective_on=now,changed_at=now,changed_by=owner.id)
        if model is History:values.update(to_status='trial_preparing',from_status='trial_preparing',entry_kind='progress')
        row=model(**values);db.add(row);db.flush();return row
    add(History,child,None)  # 初始状态没有正文，不提示。
    first=add(History,child,'子订单项目进度')
    add(Customer,child,'客户反馈')
    add(Annotator,grandchild,'标注员安排')
    parent.child_count=1;child.child_count=1;grandchild.child_count=0
    attach_counts(db,[parent,child,grandchild])
    assert (parent.child_progress_count,child.child_progress_count,grandchild.child_progress_count)==(3,1,0)
    assert len(parent.child_progress_keys)==3
    result=listing(db,parent.id,0,2)
    assert result['total']==3 and len(result['items'])==2
    assert {r['track'] for r in listing(db,parent.id,0,20)['items']}=={'project','customer','annotator'}
    assert set(listing(db,parent.id)['record_keys'])==set(parent.child_progress_keys)
    original_keys=set(parent.child_progress_keys)
    from datetime import timedelta
    first.updated_at=now+timedelta(seconds=1);first.change_note='修改后的项目进度';db.flush()
    attach_counts(db,[parent])
    assert len(set(parent.child_progress_keys)-original_keys)==1
    first.change_note='子订单项目进度';db.flush()
    # 母订单只有其他正文或其他类型的相同正文，仍需提示。
    add(Customer,parent,'子订单项目进度')
    attach_counts(db,[parent]);assert parent.child_progress_count==3
    reflected=add(History,parent,' 子订单项目进度 ')
    attach_counts(db,[parent]);assert parent.child_progress_count==2
    assert first.id not in {r['id'] for r in listing(db,parent.id)['items']}
    db.delete(reflected);db.flush()
    attach_counts(db,[parent]);assert parent.child_progress_count==3
