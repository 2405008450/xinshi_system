"""两个服务器共用的 OCR 验收程序；仅处理本目录样本，不连接业务数据库。"""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys,time
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parent))
# 兼容从项目 tools 目录执行，以及复制到服务器独立验收目录执行。
sys.path.append(str(Path(__file__).resolve().parents[1]))
from document_word_count_worker import count_file,text_statistics

def run(root):
    cases=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    versions={}
    for name in ['rapidocr_onnxruntime','rapidocr','onnxruntime','PyMuPDF','numpy']:
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:pass
    report=dict(checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),python=sys.version.split()[0],versions=versions,cases=[])
    for case in cases:
        started=time.monotonic();expected=text_statistics(case['text'])
        try:
            actual=count_file(root/case['file'])
            if actual['status']!='counted':raise ValueError(actual.get('message','统计失败'))
            errors={}
            for field in ['words','characters_no_spaces','cjk_chars_korean_words','foreign_words']:
                errors[field]=abs(actual[field]-expected[field])/expected[field] if expected[field] else (0.0 if actual[field]==0 else None)
            row=dict(name=case['file'],category=case['category'],expected=expected,
                actual={key:actual[key] for key in expected},errors=errors,
                words_passed=errors['words'] is not None and errors['words']<=.05,
                all_metrics_passed=all(value is not None and value<=.05 for value in errors.values()),
                text=actual.get('ocr_text',''),ocr_pages=actual.get('ocr_pages',[]),seconds=round(time.monotonic()-started,2))
        except Exception as exc:row=dict(name=case['file'],category=case['category'],expected=expected,error=str(exc),words_passed=False,all_metrics_passed=False,seconds=round(time.monotonic()-started,2))
        report['cases'].append(row)
        (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({key:row.get(key) for key in ['name','words_passed','all_metrics_passed','errors','seconds','error']},ensure_ascii=False),flush=True)
    report['word_count_passed']=sum(row['words_passed'] for row in report['cases'])
    report['all_metrics_passed']=sum(row['all_metrics_passed'] for row in report['cases'])
    (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'total':len(cases),'word_count_passed':report['word_count_passed'],'all_metrics_passed':report['all_metrics_passed']}))

if __name__=='__main__':run(Path(sys.argv[1]).resolve())
