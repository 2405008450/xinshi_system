from uuid import uuid4
import pytest
from work_report_hierarchy import normalize_hierarchy

def item(order='TP-1',**fields):
    return {'source_type':'manual','task_type':'项目工作','task_name':'项目','progress_content':'任务','display_metadata':{'_feedback_key':str(uuid4()),'order_no':order,'report_types':['笔译项目']}}|fields

def test_same_order_nested_and_inherits_identity_only():
    first=item();second=item(task_name='其他名字',progress_content='二级任务');third=item('TP-2')
    result=normalize_hierarchy([first,third,second])
    assert result==[first,second,third]
    assert second['display_metadata']['parent_item_key']==first['display_metadata']['_feedback_key']
    assert second['task_name']=='项目' and second['progress_content']=='二级任务'

def test_multiple_children_and_reparent_collapse_to_second_level():
    first=item();second=item();third=item()
    third['display_metadata']['parent_item_key']=second['display_metadata']['_feedback_key']
    result=normalize_hierarchy([first,second,third])
    assert len(result)==3
    assert second['display_metadata']['parent_item_key']==third['display_metadata']['parent_item_key']==first['display_metadata']['_feedback_key']

def test_cross_report_missing_parent_and_cycle_rejected():
    first=item();first['display_metadata']['parent_item_key']=str(uuid4())
    with pytest.raises(ValueError):normalize_hierarchy([first])
    first=item();second=item();first['display_metadata']['parent_item_key']=second['display_metadata']['_feedback_key'];second['display_metadata']['parent_item_key']=first['display_metadata']['_feedback_key']
    with pytest.raises(ValueError):normalize_hierarchy([first,second])


def test_child_of_new_system_event_keeps_parent_key_when_rederived():
    from task_service import merge_daily_report_items
    from work_report_collaboration import assign_item_keys
    event=item(source_type='system_event');event['source_id']=uuid4()
    child=item();child['display_metadata']['parent_item_key']=event['display_metadata']['_feedback_key']
    derived={**event,'display_metadata':{'order_no':'TP-1'}}
    merged=merge_daily_report_items([event,child],[derived])
    assign_item_keys(uuid4(),merged)
    normalized=normalize_hierarchy(merged)
    assert normalized[0]['source_type']=='system_event'
    assert normalized[1]['display_metadata']['parent_item_key']==normalized[0]['display_metadata']['_feedback_key']


def test_rederived_existing_event_preserves_feedback_key_and_child_link():
    from types import SimpleNamespace
    from work_report_collaboration import assign_item_keys
    old=item(source_type='system_event');old['source_id']=uuid4()
    previous=SimpleNamespace(**old,id=uuid4())
    fresh={**old,'display_metadata':{**old['display_metadata'],'_feedback_key':str(uuid4())}}
    child=item();child['display_metadata']['parent_item_key']=fresh['display_metadata']['_feedback_key']
    assign_item_keys(uuid4(),[fresh,child],[previous])
    assert fresh['display_metadata']['_feedback_key']==old['display_metadata']['_feedback_key']
    assert child['display_metadata']['parent_item_key']==old['display_metadata']['_feedback_key']
