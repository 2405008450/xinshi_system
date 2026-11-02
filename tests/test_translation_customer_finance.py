from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import HTTPException
from tests.test_chat_participant_access import environment
from tests.test_arrangement_order_targets import orders
from word_count_models import WordCountMetric
import translation_customer_finance as finance


def setup(db, owner):
    root,child,third,_=orders(db,owner)
    old_number=root.order_no;root.order_no='TP-261101-001'
    child.sub_order_no=child.sub_order_no.replace(old_number,root.order_no)
    third.sub_order_no=third.sub_order_no.replace(old_number,root.order_no)
    for row,count in [(root,999),(child,300),(third,20)]:
        for metric,value in [('characters_no_spaces',count),('documents',2),('pages',4)]:
            db.add(WordCountMetric(id=uuid4(),project_id=row.id if row is root else None,sub_order_id=None if row is root else row.id,dimension='customer',metric_type=metric,count_value=value))
    db.commit()
    return root,child,third


def write(db,owner,root,order,amount,**kwargs):
    data=finance.read(db,root.id)
    return finance.save(db,owner,root.id,finance.PriceWrite(version=data['version'],order_id=order.id,amount=amount,**kwargs))


def test_inherit_tree_leaf_rollup_override_and_reprice(environment):
    db,(owner,_,_)=environment;root,child,third=setup(db,owner)
    data=write(db,owner,root,root,'0.5')
    assert data['item']['totals']=={'CNY':'10.00'} # 仅最低层计入，避免999+300+20重复。
    assert data['item']['children'][0]['children'][0]['amount']=='0.5'
    data=write(db,owner,root,third,'1')
    assert data['item']['totals']=={'CNY':'20.00'}
    data=write(db,owner,root,root,'0.8')
    assert data['item']['children'][0]['amount']=='0.8'
    assert data['item']['children'][0]['children'][0]['amount']=='1' # 单独修改保留。
    assert data['item']['totals']=={'CNY':'20.00'}


@pytest.mark.parametrize('metric,expected',[('documents','6.00'),('pages','12.00')])
def test_documents_pages_zero_and_missing(environment,metric,expected):
    db,(owner,_,_)=environment;root,child,third=setup(db,owner)
    data=write(db,owner,root,root,'3',metric=metric)
    assert data['item']['totals']=={'CNY':expected}
    data=write(db,owner,root,third,'0',metric=metric,currency='USD')
    assert data['item']['totals']=={'USD':'0.00'}
    db.query(WordCountMetric).filter_by(sub_order_id=third.id,metric_type=metric).delete();db.commit()
    data=finance.read(db,root.id)
    assert data['item']['incomplete'] and not data['item']['totals']


def test_foreign_order_stale_and_decimal_rounding(environment):
    db,(owner,_,_)=environment;root,child,third=setup(db,owner)
    before=finance.read(db,root.id)
    data=write(db,owner,root,root,'0.1234')
    assert data['item']['totals']=={'CNY':'2.47'}
    with pytest.raises(HTTPException) as stale:finance.save(db,owner,root.id,finance.PriceWrite(version=before['version'],order_id=root.id,amount=1))
    assert stale.value.status_code==409;db.rollback()
    with pytest.raises(HTTPException) as foreign:write(db,owner,root,type('Order',(),{'id':uuid4()})(),1)
    assert foreign.value.status_code==422


def test_new_child_inherits_without_adjustments(environment):
    from models import TranslationSubOrder
    db,(owner,_,_)=environment;root,_,_=setup(db,owner)
    write(db,owner,root,root,'2',adjusted_total='100',explanation='说明')
    child=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.002',sub_project_name='新文件.docx')
    db.add(child);db.flush();finance.inherit_new_order(db,child);db.flush()
    assert finance.primary(child).unit_price_excl_tax==Decimal('2')
    assert finance.primary(child).total_excl_tax is None


def test_filters_and_client_subtotals_cover_all_pages(environment):
    from models import Client
    db,(owner,_,_)=environment;root,child,third=setup(db,owner)
    client=Client(id=uuid4(),client_name='甲测试公司',client_short_name='甲客户',client_manager='客户经理甲')
    db.add(client);root.client_id=client.id;db.commit()
    write(db,owner,root,root,'0.5',billing_month='2026-11')
    data=finance.page(skip=0,limit=1,keyword=None,project_status=None,billing_month='2026-11',client='测试 甲',client_manager='经理 甲',db=db)
    assert data['total']==1 and len(data['items'])==1
    assert data['client_subtotals'][0]['totals']=={'CNY':'10.00'}
    assert finance.page(skip=0,limit=1,keyword=None,project_status=None,billing_month='2026-10',client=None,client_manager=None,db=db)['total']==0
    assert finance.page(skip=0,limit=1,keyword=None,project_status=None,billing_month=None,client=None,client_manager='其他',db=db)['total']==0
    # 移至不存在的分页也保留全量客户小计。
    second=finance.page(skip=10,limit=1,keyword=None,project_status=None,billing_month='2026-11',client=None,client_manager=None,db=db)
    assert not second['items'] and second['client_subtotals'][0]['totals']=={'CNY':'10.00'}


def test_order_number_month_includes_descendants_regardless_of_charge_month(environment):
    from models import TranslationSubOrder
    db,(owner,_,_)=environment;root,child,third=setup(db,owner)
    write(db,owner,root,root,'0.5',billing_month='2026-11')
    write(db,owner,root,third,'1',billing_month='2026-10')
    sibling=TranslationSubOrder(id=uuid4(),parent_project_id=root.id,sub_order_no=root.order_no+'.002',sub_project_name='第二份.docx')
    db.add(sibling);db.flush();finance.inherit_new_order(db,sibling)
    db.add(WordCountMetric(id=uuid4(),sub_order_id=sibling.id,dimension='customer',metric_type='characters_no_spaces',count_value=10));db.commit()
    finance.read(db,root.id)
    loaded=finance.crud.get_translation_project(db,root.id)
    assert finance.tree(loaded)['item']['totals']=={'CNY':'25.00'}
    assert finance.tree(loaded,'2026-11')['item']['totals']=={'CNY':'25.00'}
    assert finance.tree(loaded,'2026-10')['item']['totals']=={}


def test_only_mine_uses_latest_manager_id_and_exact_legacy_name(environment):
    from models import Client,TranslationProject
    from project_client_manager import ProjectClientManagerChange
    from annotation_progress_time import business_now
    db,(owner,member,_)=environment
    client=Client(id=uuid4(),client_name='自己负责的客户',client_short_name='本人客户',client_manager=owner.full_name)
    db.add(client);db.flush()
    projects=[TranslationProject(id=uuid4(),order_no=f'TP-SELF-{index}',project_name='测试.docx',client_id=client.id) for index in range(4)]
    db.add_all(projects);db.flush()
    for project,manager_id,name in [(projects[1],member.id,owner.full_name),(projects[2],owner.id,'经理旧姓名'),(projects[3],None,None)]:
        db.add(ProjectClientManagerChange(project_type='translation',project_id=project.id,revision=1,new_manager_id=manager_id,new_manager_name=name,actor_user_id=owner.id,actor_name=owner.full_name,reason='隔离测试',changed_at=business_now()))
    db.commit()
    kwargs=dict(skip=0,limit=10,keyword=None,project_status=None,billing_month=None,client=None,client_manager=None,db=db,user=owner)
    data=finance.page(**kwargs,only_mine=True)
    assert {row['id'] for row in data['items']}=={str(projects[0].id),str(projects[2].id)}
    assert data['total']==2 and sum(row['project_count'] for row in data['client_subtotals'])==2
    assert finance.page(**kwargs,only_mine=False)['total']==4
