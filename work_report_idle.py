"""工作报告空闲时间及声明；时长独立于工作任务耗时。"""
DECLARATION_VERSION = 1
DECLARATION_TEXT = '本人确认，在休息时间，没有进行违反公司规定和员工手册规定的行为，包括但不限于玩电脑/手机游戏、观看电脑/手机视频、阅读各种形式的小说和其他不合适的娱乐行为。如有违反，愿意放弃公司的一切福利、奖金（含年终奖）等。本人且知悉，该等行为属于重大违反公司规定的行为。'


def declaration_data(report):
    from chat_time import api_time
    row=report.idle_declaration if report else None
    return dict(idle_minutes=row.idle_minutes if row else None,idle_declaration_confirmed=bool(row and row.confirmed),idle_declaration_text=row.declaration_text if row else None,idle_confirmed_at=api_time(row.confirmed_at) if row else None)


def save_declaration(report,payload):
    if payload.idle_minutes is None:return
    if payload.idle_declaration_confirmed is not True:raise ValueError('请勾选确认空闲时间声明')
    from task_models import DailyReportIdleDeclaration
    from chat_time import now
    if report.idle_declaration is None:report.idle_declaration=DailyReportIdleDeclaration(report_id=report.id)
    row=report.idle_declaration
    # 原样保存时保留原确认时刻；修订时记录新时刻，旧内容由报告修订快照保留。
    if row.idle_minutes!=payload.idle_minutes or row.declaration_version!=DECLARATION_VERSION:
        row.confirmed_at=now()
    row.idle_minutes=payload.idle_minutes;row.confirmed=True;row.declaration_text=DECLARATION_TEXT;row.declaration_version=DECLARATION_VERSION
