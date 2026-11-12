"""对照迁移前留存的真实文件验收结果；只读原文件，不连接业务数据库。"""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from document_word_count_worker import count_file
samples=json.loads(Path('E:/fastapi-llm-demo/output/word_count_acceptance_v4_sample/server_results.json').read_text(encoding='utf-8'))
folder=Path('artifacts/document-word-count');folder.mkdir(parents=True,exist_ok=True)
rows=[]
for sample in samples:
    if sample['extension'] not in {'.docx','.xlsx','.pptx'}:continue
    try:
        result=count_file(Path(sample['local_path']))
        expected=sample['result']['main_word_count']
        actual=result.get('words')
        difference=abs(actual-expected)/expected if expected and actual is not None else None
        row=dict(name=sample['name'],type=sample['extension'],expected=expected,actual=actual,difference=difference,passed=difference is not None and difference<=.05)
    except Exception as exc:row=dict(name=sample['name'],type=sample['extension'],passed=False,error=str(exc))
    rows.append(row)
    (folder/'samples.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(row,ensure_ascii=False),flush=True)
assert len(rows)==32 and all(r['passed'] for r in rows)
