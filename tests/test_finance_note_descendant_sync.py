from uuid import uuid4
import pytest
from fastapi import HTTPException
from models import TranslationSubOrder
from tests.test_customer_statements import context,project
from tests.test_chat_participant_access import environment
import translation_finance_notes as notes


def hierarchy(context):
    _,db,clients,_,user=context
    root=project(db,clients[0],'SYNC')
    children=[TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+suffix,sub_project_name='多级子订单') for suffix in ['.001','.001.001','.001.001.001','.002']]
    db.add_all(children);db.commit();db.refresh(root)
    return db,user,root,children


def test_parent_save_physically_synchronizes_all_levels_and_keeps_note_types_separate(context):
    db,user,root,children=hierarchy(context)
    notes.apply(db,user,root,root,customer='对外说明',internal='内部安排');db.commit()
    for owner in [root,*children]:
        row=db.get(notes.TranslationFinanceNote,owner.id)
        assert row.customer_note=='对外说明' and row.internal_note=='内部安排'
    with pytest.raises(HTTPException) as failure:notes.apply(db,user,root,children[0],customer='分支说明')
    assert failure.value.status_code==409
    detail=failure.value.detail
    assert {row['order_id'] for row in detail['overwrites']}=={str(children[1].id),str(children[2].id)}
    assert db.get(notes.TranslationFinanceNote,children[0].id).customer_note=='对外说明'
    db.info['finance_note_sync_plans']=[detail['plan']]
    notes.apply(db,user,root,children[0],customer='分支说明');db.commit()
    assert [db.get(notes.TranslationFinanceNote,owner.id).customer_note for owner in children]==['分支说明','分支说明','分支说明','对外说明']
    assert all(db.get(notes.TranslationFinanceNote,owner.id).internal_note=='内部安排' for owner in children)


def test_changed_descendant_content_invalidates_previous_confirmation(context):
    db,user,root,children=hierarchy(context)
    notes.apply(db,user,root,children[2],customer='子订单已有内容');db.commit()
    with pytest.raises(HTTPException) as first:notes.apply(db,user,root,root,customer='母订单新内容')
    db.info['finance_note_sync_plans']=[first.value.detail['plan']]
    notes.apply(db,user,root,children[2],customer='子订单随后修改');db.commit()
    with pytest.raises(HTTPException) as changed:notes.apply(db,user,root,root,customer='母订单新内容')
    assert changed.value.detail['plan']!=first.value.detail['plan']
    assert changed.value.detail['overwrites'][0]['before']=='子订单随后修改'
    assert db.get(notes.TranslationFinanceNote,root.id) is None
