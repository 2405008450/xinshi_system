"""Build an attributed offline location catalog from CSC and China administrative divisions."""
import gzip,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build():
    folder=ROOT/'tmp/geography'
    countries=json.loads((folder/'countries.json').read_text(encoding='utf8'))
    states=json.loads((folder/'states.json').read_text(encoding='utf8'))
    cities=json.loads(gzip.decompress((folder/'cities.json.gz').read_bytes()))
    rows=[];cs={};ss={}
    def name(row):return (row.get('translations') or {}).get('zh-CN') or row['name']
    def add(key,level,path,alias=''):
        rows.append([str(key),level,*path,alias])
    for c in countries:
        cs[c['id']]=name(c);add('c'+str(c['id']),'country',[name(c),'','',''],c['name']+' '+c['iso2']+' '+c['iso3'])
    for s in states:
        ss[s['id']]=(cs.get(s['country_id'],s.get('country_name','')),name(s))
        if s['country_code']!='CN':add('s'+str(s['id']),'province',[*ss[s['id']],'',''],s['name'])
    for c in cities:
        if c.get('country_code')=='CN':continue
        country=cs.get(c['country_id'],'');state=ss.get(c.get('state_id'),(country,''))[1]
        add('t'+str(c['id']),'city',[country,state,name(c),''],c['name'])
    china=next(name(c) for c in countries if c['iso2']=='CN')
    for p in json.loads((folder/'china.json').read_text(encoding='utf8')):
        add('cn'+p['code'],'province',[china,p['name'],'',''])
        for city in p.get('children',[]):
            add('cn'+city['code'],'city',[china,p['name'],city['name'],''])
            for d in city.get('children',[]):add('cn'+d['code'],'district',[china,p['name'],city['name'],d['name']])
    target=ROOT/'data/geography/catalog.json.gz';target.write_bytes(gzip.compress(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    print('rows=',len(rows),'countries=',len(countries),'compressed_bytes=',target.stat().st_size)
if __name__=='__main__':build()
