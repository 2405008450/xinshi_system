"""客户/子客户对账单主体的唯一配置，复用工作区 JSON 与修改历史。"""
from copy import deepcopy

from fastapi import HTTPException
from sqlalchemy import inspect

KEY = 'statement_subject_defaults'


def read(db, client_id, sub_client_id=None):
    from customer_statement_workspace import StatementWorkspace
    if not inspect(db.connection()).has_table(StatementWorkspace.__tablename__):
        return None
    row = db.get(StatementWorkspace, client_id)
    return (row.payload if row else {}).get(KEY, {}).get(str(sub_client_id or 'client'))


def apply(db, payload, subject_key, sub_client_id=None, *, only_new=False):
    from invoice_parties import SUBJECTS
    import customer_statements as source
    if subject_key is not None and subject_key not in SUBJECTS:
        raise HTTPException(422, '请选择有效的对账单主体')
    defaults = payload.setdefault(KEY, {})
    scope = str(sub_client_id or 'client')
    if subject_key is None:
        defaults.pop(scope, None)
        _, company = source.statement_company_settings(db)
        subject_key = next((key for key, (_, name) in SUBJECTS.items() if name == company), None)
        if subject_key is None:
            return
    else:
        defaults[scope] = subject_key
    settings, _ = source.statement_company_settings(db, subject_key)
    fields = {'company': SUBJECTS[subject_key][1], 'subject_key': subject_key}
    if source.private_statement_settings_available() and settings:
        fields.update({key: getattr(settings, key) for key in source.PRIVATE_STATEMENT_FIELDS})
    else:
        # 切换主体时不能沿用另一主体的银行账号或印章。
        fields.update({key: '' for key in source.PRIVATE_STATEMENT_FIELDS})
    for board in payload['boards']:
        if board.get('settlement_scope')=='special':continue
        if str(board.get('sub_client_id') or 'client') == scope:
            if not only_new or board['fields'].get('subject_key') != subject_key:
                board['fields'].update(fields)


def write(db, user, client_id, subject_key, sub_client_id=None):
    from customer_statement_workspace import workspace, empty_payload, save
    row = workspace(db, client_id, lock=True)
    before = deepcopy(row.payload if row else empty_payload())
    payload = deepcopy(before)
    apply(db, payload, subject_key, sub_client_id)
    if before != payload:
        save(db, user, client_id, row, before, payload, '同步对账单主体', {
            'sub_client_id': str(sub_client_id) if sub_client_id else None,
            'before': before.get(KEY, {}).get(str(sub_client_id or 'client')),
            'after': subject_key,
        }, commit=False)


def apply_defaults(db, payload):
    for scope, subject_key in list(payload.get(KEY, {}).items()):
        apply(db, payload, subject_key, None if scope == 'client' else scope, only_new=True)
