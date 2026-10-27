from uuid import uuid4
from datetime import datetime
from test_chat_participant_access import environment
from models import TranslationProject,Translator
from manuscript_models import ManuscriptArrangement,ManuscriptDispatch
from translation_project_sorting import translator_name_key,translator_name_sort_expression

def test_phonetic_name_keys_mix_chinese_english_and_ignore_case():
    names=['张三','bob','Alice','李四','王五']
    assert sorted(names,key=translator_name_key)==['Alice','bob','李四','王五','张三']
    assert translator_name_key('Émile')==translator_name_key('emile')

def test_global_translator_order_before_paging_and_nulls_last(environment):
    db,_=environment
    projects=[]
    for index,names in enumerate([['张三'],['Bob'],['李四','Alice'],[]]):
        project=TranslationProject(id=uuid4(),order_no=f'TP-NAME-{index}',project_name='排序测试')
        db.add(project);db.flush();projects.append(project)
        dispatch=ManuscriptDispatch(id=uuid4(),translation_project_id=project.id,status='confirmed',confirmed_at=datetime(2026,10,25))
        db.add(dispatch);db.flush()
        for name in names:
            translator=Translator(id=uuid4(),translator_name=name);db.add(translator);db.flush()
            db.add(ManuscriptArrangement(id=uuid4(),dispatch_id=dispatch.id,translation_project_id=project.id,translator_id=translator.id,translator_name_snapshot=name,status='confirmed'))
        # 取消的译员不参与排序。
        db.add(ManuscriptArrangement(id=uuid4(),dispatch_id=dispatch.id,translation_project_id=project.id,translator_id=uuid4(),translator_name_snapshot='AAA',status='cancelled'))
    db.commit()
    query=db.query(TranslationProject)
    rank=translator_name_sort_expression(db,query)
    assert [row.id for row in query.order_by(rank.asc().nullslast())]==[projects[2].id,projects[1].id,projects[0].id,projects[3].id]
    assert [row.id for row in query.order_by(rank.desc().nullslast()).offset(1).limit(2)]==[projects[1].id,projects[2].id]
