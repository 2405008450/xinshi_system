import gzip,json,unicodedata
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter,Depends,Query
from routers.auth import require_permission

router=APIRouter(prefix='/geography',tags=['地区目录'])
@lru_cache(maxsize=1)
def catalog():
    rows=json.loads(gzip.decompress((Path(__file__).parent/'data/geography/catalog.json.gz').read_bytes()))
    return [(r,unicodedata.normalize('NFKC',' '.join(r[2:])).casefold()) for r in rows]

@router.get('/search')
def search(q:str='',level:str='country',country:str='',province:str='',city:str='',skip:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=500),user=Depends(require_permission('clients:read'))):
    terms=unicodedata.normalize('NFKC',q).casefold().split()
    matches=[]
    for row,text in catalog():
        if terms:
            if not all(term in text for term in terms):continue
        elif row[1]!=level or (level!='country' and country and row[2]!=country) or (level in ('city','district') and province and row[3]!=province) or (level=='district' and city and row[4]!=city):continue
        matches.append(row)
    matches.sort(key=lambda r:(0 if terms and q.casefold() in [v.casefold() for v in r[2:6]] else 1,len([v for v in r[2:6] if v]),r[2:6]))
    return {'total':len(matches),'items':[dict(id=r[0],level=r[1],country=r[2],province=r[3],city=r[4],district=r[5],label=' / '.join(v for v in r[2:6] if v)) for r in matches[skip:skip+limit]]}
