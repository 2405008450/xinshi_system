from tests.test_customer_statement_workspace import setup,imported,change
from tests.test_customer_statements import context
from tests.test_chat_participant_access import environment
import translation_finance_notes as notes


def test_statement_notes_use_live_customer_notes_and_edit_finance_in_same_transaction(setup):
    http,db,clients,_,user,first,_=setup
    notes.apply(db,user,first,first,customer='客户可见说明',internal='内部说明不外传');db.commit()
    state=imported(setup,['2026-10'])
    board=state['documents'][0];line=board['statement']['rows'][0]
    assert line['remarks']=='客户可见说明'
    state=change(setup,state,'edit_customer_note',{'board_id':board['id'],'row_id':line['_row_id'],'customer_note':'对账单上修改的说明'})
    note=db.get(notes.TranslationFinanceNote,first.id)
    assert note.customer_note=='对账单上修改的说明'
    assert note.internal_note=='内部说明不外传'
    assert first.customer_charge_items[0].remarks=='内部说明不外传'
    assert state['documents'][0]['statement']['rows'][0]['remarks']==note.customer_note
    notes.apply(db,user,first,first,customer='财务中再次修改');db.commit()
    current=http.get(f"/translation-statement-workspaces/{clients[0].id}").json()
    assert current['documents'][0]['statement']['rows'][0]['remarks']=='财务中再次修改'
    state=change(setup,current,'edit_customer_note',{'board_id':board['id'],'row_id':line['_row_id'],'customer_note':''})
    assert db.get(notes.TranslationFinanceNote,first.id).customer_note==''
    assert state['documents'][0]['statement']['rows'][0]['remarks']==''


def test_note_sync_keeps_revision_and_content_access_protection(setup):
    state=imported(setup,['2026-10']);board=state['documents'][0];row=board['statement']['rows'][0]
    changed=change(setup,state,'edit_customer_note',{'board_id':board['id'],'row_id':row['_row_id'],'customer_note':'新说明'})
    change(setup,state,'edit_customer_note',{'board_id':board['id'],'row_id':row['_row_id'],'customer_note':'过期说明'},expected=409)
    change(setup,changed,'edit_customer_note',{'board_id':board['id'],'row_id':'不存在','customer_note':'不能写入'},expected=409)


def test_archive_freezes_latest_customer_note_and_does_not_follow_later_finance_changes(setup):
    http,db,clients,_,user,first,_=setup
    notes.apply(db,user,first,first,customer='初始说明');db.commit()
    state=imported(setup,['2026-10']);board=state['documents'][0]
    notes.apply(db,user,first,first,customer='废除时最新说明');db.commit()
    state=change(setup,state,'set_board_status',{'board_id':board['id'],'status':'void'})
    path=f"/translation-statement-workspaces/{clients[0].id}/historical-versions"
    uid=http.get(path).json()['items'][0]['id']
    notes.apply(db,user,first,first,customer='废除后另改说明');db.commit()
    archived=http.get(path+'/'+uid).json()['documents'][0]['statement']
    assert archived['rows'][0]['remarks']=='废除时最新说明'
