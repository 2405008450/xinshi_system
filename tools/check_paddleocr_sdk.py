"""在本项目解释器中实测 PaddleOCR SDK，不连接业务数据库、不替换默认 OCR 引擎。"""
import os
os.environ.setdefault('PADDLE_PDX_MODEL_SOURCE','bos')
os.environ.setdefault('PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK','True')
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
import time
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from file_word_counter import count_text

def check():
    import paddle
    from paddleocr import PaddleOCR
    from PIL import Image,ImageDraw,ImageFont
    import pymupdf
    root=Path(__file__).resolve().parents[1]/'artifacts/document-word-count/paddle-sdk'
    root.mkdir(parents=True,exist_ok=True)
    report=dict(checked_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),python=sys.version,
        executable=sys.executable,versions={key:metadata.version(key) for key in ['paddlepaddle','paddleocr','paddlex','numpy']},
        device='cpu',cuda_compiled=paddle.device.is_compiled_with_cuda())
    paddle.set_device('cpu')
    paddle.utils.run_check()
    report['framework_check']=True
    image=Image.new('RGB',(1400,260),'white');draw=ImageDraw.Draw(image)
    fonts=['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    font=ImageFont.truetype(next(path for path in fonts if Path(path).is_file()),64)
    draw.text((35,20),'字数统计环境测试',fill='black',font=font)
    draw.text((35,120),'Word count test 123',fill='black',font=font)
    image.save(root/'scan.png')
    pdf=pymupdf.open();page=pdf.new_page(width=700,height=130);page.insert_image(page.rect,filename=str(root/'scan.png'));pdf.save(root/'scan.pdf');pdf.close()
    configuration=dict(device='cpu',text_detection_model_name='PP-OCRv5_mobile_det',
        text_recognition_model_name='PP-OCRv5_mobile_rec',use_doc_orientation_classify=False,
        use_doc_unwarping=False,use_textline_orientation=False,cpu_threads=2,enable_mkldnn=False)
    report['configuration']=configuration
    started=time.monotonic();engine=PaddleOCR(**configuration)
    report['initialization_seconds']=round(time.monotonic()-started,2)
    report['samples']=[]
    for name in ['scan.png','scan.pdf']:
        started=time.monotonic();lines=[];scores=[]
        for result in engine.predict(str(root/name)):
            value=result.json
            if isinstance(value,str):value=json.loads(value)
            value=value.get('res',value)
            lines.extend(value.get('rec_texts',[]));scores.extend(float(s) for s in value.get('rec_scores',[]))
        text='\n'.join(lines);normalized=''.join(text.split())
        row=dict(file=name,text=text,words=count_text(text).word_count,scores=scores,
            seconds=round(time.monotonic()-started,2),passed='字数统计环境测试' in normalized and 'Wordcounttest123' in normalized)
        report['samples'].append(row)
    report['passed']=report['framework_check'] and all(row['passed'] for row in report['samples'])
    (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report['passed']

if __name__=='__main__':
    try:passed=check()
    except Exception as exc:
        root=Path(__file__).resolve().parents[1]/'artifacts/document-word-count/paddle-sdk'
        root.mkdir(parents=True,exist_ok=True)
        (root/'failure.json').write_text(json.dumps(dict(error=type(exc).__name__,message=str(exc)),ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    raise SystemExit(0 if passed else 1)
