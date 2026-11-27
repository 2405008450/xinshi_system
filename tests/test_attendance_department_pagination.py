"""考勤明细按部门分页及整体累计一致性，使用隔离 SQLite。"""
from datetime import date
from uuid import uuid4
from test_chat_participant_access import environment
from test_monthly_shift import setup
from test_attendance import at
from attendance_models import AttendanceClockSession
import attendance_service as service


def test_department_order_before_pagination_and_totals_are_not_page_totals(environment):
    db,users=environment;setup(db,users)
    users[2].department='IT部';db.commit()
    for person,count in [(users[1],12),(users[2],13)]:
        for day in range(1,count+1):
            stamp=f'2026-11-{day:02}'
            db.add(AttendanceClockSession(id=uuid4(),user_id=person.id,day=date(2026,11,day),segment=0,check_in=at(stamp+'T09:00'),check_out=at(stamp+'T18:30'),shift_snapshot={'code':'early','label':'早班','periods':['09:00–12:00','13:30–18:30']},confirmations={}))
    db.commit()
    pages=[service.attendance_report(db,users[0],date(2026,11,1),'month',admin=True,page=page,limit=10) for page in (1,2,3)]
    assert all(page['total']==25 for page in pages)
    assert pages[0]['totals']==pages[1]['totals']==pages[2]['totals']
    rows=[row for page in pages for row in page['records']]
    assert len({(row['user_id'],row['day']) for row in rows})==25
    assert [row['department_name'] for row in rows]==['IT部']*13+['销售部']*12
    assert rows[0]['day']=='2026-11-13' and rows[13]['day']=='2026-11-12'
    assert pages[0]['department_names'][str(users[1].id)]=='销售部'
    own=service.attendance_report(db,users[1],date(2026,11,1),'month',limit=10)
    assert str(users[2].id) not in own['department_names']
    assert own['total']==12
