"""核重的新简历及结算字段：独立字段比对，原始记录完整快照。"""
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import object_session

from talent_resume_profile import TalentResumeProfile, TalentResumeProfileInput
from talent_settlement import TalentSettlement

AUX_MODELS = {'resume_profile': TalentResumeProfile, 'settlement': TalentSettlement}
RESUME_LABELS = {
    'resume_year':'简历年份', 'self_assessment':'自我评价', 'job_intention':'求职意向',
    'other_skills':'其他技能', 'interests':'兴趣爱好', 'awards_honors':'奖励和荣誉',
    'professional_domains':'专业领域（本人自述）', 'training':'培训经历',
    'campus_positions':'校内职务', 'campus_awards':'校内奖励', 'internships':'实习经历',
    'annotation':'标注经历', 'interpretation':'口译经历', 'translation':'笔译经历',
    'other':'其他经历', 'cat_tools':'常用CAT经验', 'name':'姓名', 'professional_title':'职业头衔',
    'gender':'性别', 'birth_date':'出生日期', 'nationality':'国籍', 'residence':'现居地',
    'native_place':'主要成长地', 'employment_status':'职业状态', 'highest_education':'最高学历',
    'height':'身高', 'eyesight':'视力', 'languages':'语言', 'language_notes':'语言说明',
    'certificates':'证书', 'skills':'技能', 'educations':'教育经历', 'education_periods':'教育经历时间段',
}
SETTLEMENT_LABELS = {
    'bank_account':'银行账号', 'paypal_account':'PayPal账号', 'payoneer_account':'Payoneer账号',
    'wechat_payment_code':'微信收款码', 'alipay_payment_code':'支付宝收款码',
    'invoice_available':'可开票', 'invoice_entity':'开票主体',
    'gig_platform_calculation':'零工平台核算', 'prices':'报价明细',
}


def auxiliary_rows(person):
    db = object_session(person) if hasattr(person, '_sa_instance_state') else None
    if db is None:
        return {}
    return {key: db.get(model, person.id, populate_existing=True) for key, model in AUX_MODELS.items()}


def auxiliary_snapshot(person, columns):
    return {key: columns(row) if row is not None else None for key, row in auxiliary_rows(person).items()}


def auxiliary_values(person, plain, digest):
    result = {}

    def value_for(key, value):
        # 相同经历按内容去重，稳定生成ID，使重复预览及提交的令牌一致。
        if isinstance(value, list):
            rows = []
            for item in value:
                if isinstance(item, dict):
                    item = {k:v for k,v in item.items() if k != 'id'}
                    item = {**item, 'id':str(uuid5(NAMESPACE_URL, digest([key, item])))}
                if item not in rows:
                    rows.append(item)
            return rows
        return value

    for section, row in auxiliary_rows(person).items():
        if row is None:
            continue
        if section == 'resume_profile':
            for key in TalentResumeProfileInput.model_fields:
                if key in {'revision', 'versions'} or key not in row.data:
                    continue
                path = f'{section}.{key}'
                result[path] = value_for(path, plain(row.data[key]))
            for locale, version in (row.data.get('versions') or {}).items():
                for key, value in version.items():
                    path = f'{section}.versions.{locale}.{key}'
                    result[path] = value_for(path, plain(value))
        else:
            for key in SETTLEMENT_LABELS:
                path = f'{section}.{key}'
                result[path] = value_for(path, plain(getattr(row, key)))
    return result


def auxiliary_label(key):
    parts = key.split('.')
    if parts[0] == 'settlement':
        return '商务与结算：' + SETTLEMENT_LABELS.get(parts[-1], parts[-1])
    prefix = '中文简历'
    if len(parts) > 3 and parts[1] == 'versions':
        prefix = '英文简历' if parts[2] == 'en' else f'外文简历（{parts[2]}）'
    return prefix + '：' + RESUME_LABELS.get(parts[-1], parts[-1])


def set_nested(data, path, value):
    parts = path.split('.')
    for key in parts[:-1]:
        data = data.setdefault(key, {})
    data[parts[-1]] = value


def get_nested(model, path):
    for key in path.split('.'):
        model = model.get(key) if isinstance(model, dict) else getattr(model, key)
    return model


def apply_auxiliary(db, target, payload, actor):
    from talent_resume_profile import save_resume_profile
    from talent_settlement import save_settlement
    save_resume_profile(db, target, payload, actor)
    save_settlement(db, target, payload, actor)


def restore_auxiliary(db, person_id, before, after, typed):
    for key, model in AUX_MODELS.items():
        # 旧操作没有保存这部分资料，不能据此清空现有记录。
        if key not in before or before[key] == after.get(key):
            continue
        row = db.get(model, person_id)
        original = before[key]
        if original is None:
            if row is not None:
                db.delete(row)
        else:
            if row is None:
                row = model(person_id=person_id)
                db.add(row)
            for column in model.__table__.columns:
                setattr(row, column.key, typed(column, original[column.key]))
