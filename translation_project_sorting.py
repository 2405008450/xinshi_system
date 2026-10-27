"""全量结果的译员字母排序；先生成名称排名，数据库排序后再分页。"""
from functools import lru_cache
import unicodedata
from pypinyin import lazy_pinyin
from sqlalchemy import Integer,case,cast,func,literal,select
from sqlalchemy.dialects.postgresql import JSONB
from models import TranslationProject,Translator
from manuscript_models import ManuscriptArrangement,ManuscriptDispatch

@lru_cache(maxsize=8192)
def translator_name_key(name):
    phonetic=''.join(lazy_pinyin(str(name or '').strip())).casefold()
    return ''.join(char for char in unicodedata.normalize('NFKD',phonetic) if not unicodedata.combining(char))

def assignment_conditions():
    return (ManuscriptArrangement.translation_project_id==TranslationProject.id,
            ManuscriptArrangement.sub_order_id.is_(None),ManuscriptArrangement.status!='cancelled',
            ManuscriptDispatch.status!='cancelled',ManuscriptDispatch.confirmed_at.is_not(None))

def translator_name_sort_expression(db,filtered_projects):
    ids=select(filtered_projects.with_entities(TranslationProject.id).order_by(None).subquery().c.id)
    names=db.query(ManuscriptArrangement.translator_name_snapshot).join(ManuscriptDispatch,ManuscriptDispatch.id==ManuscriptArrangement.dispatch_id).filter(
        ManuscriptArrangement.translation_project_id.in_(ids),ManuscriptArrangement.sub_order_id.is_(None),
        ManuscriptArrangement.status!='cancelled',ManuscriptDispatch.status!='cancelled',ManuscriptDispatch.confirmed_at.is_not(None))
    legacy=db.query(Translator.translator_name).join(TranslationProject,TranslationProject.translator_id==Translator.id).filter(TranslationProject.id.in_(ids))
    values={name for name, in names.union(legacy).all() if name and name.strip()}
    keys=sorted({translator_name_key(name) for name in values})
    ranks={key:index for index,key in enumerate(keys)}
    mapping={name:ranks[translator_name_key(name)] for name in values}
    if not mapping:return literal(None,type_=Integer)
    def rank(column):
        if db.get_bind().dialect.name=='postgresql':
            # JSONB 排名表仅使用一个绑定参数，避免大量名称使 SQL 参数数量超限。
            return cast(literal(mapping,type_=JSONB).op('->>')(column),Integer)
        return case(mapping,value=column,else_=None)
    assigned=select(func.min(rank(ManuscriptArrangement.translator_name_snapshot))).join(
        ManuscriptDispatch,ManuscriptDispatch.id==ManuscriptArrangement.dispatch_id).where(*assignment_conditions()).correlate(TranslationProject).scalar_subquery()
    fallback=select(rank(Translator.translator_name)).where(Translator.id==TranslationProject.translator_id).correlate(TranslationProject).scalar_subquery()
    return func.coalesce(assigned,fallback)
