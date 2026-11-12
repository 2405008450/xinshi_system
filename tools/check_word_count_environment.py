"""隔离检查转换和 CPU OCR 环境，不导入主应用、不连接数据库。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

def check():
    from docx import Document
    from openpyxl import Workbook
    from pptx import Presentation
    from pptx.util import Inches
    from PIL import Image, ImageDraw, ImageFont
    import pymupdf
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    soffice=os.getenv('LIBREOFFICE_PATH') or shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice and Path('C:/Program Files/LibreOffice/program/soffice.exe').is_file():
        soffice='C:/Program Files/LibreOffice/program/soffice.exe'
    if not soffice:raise RuntimeError('LibreOffice missing')
    if os.name=='nt' and Path(soffice).with_suffix('.com').is_file():soffice=str(Path(soffice).with_suffix('.com'))
    report={'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'python':sys.version.split()[0], 'libreoffice':'', 'conversion':{}}
    with tempfile.TemporaryDirectory(prefix='xinshi-wordcount-env-') as temporary:
        root=Path(temporary);legacy=root/'legacy';legacy.mkdir();restored=root/'restored';restored.mkdir()
        report['libreoffice']=subprocess.check_output([soffice,'-env:UserInstallation='+(root/'profile').as_uri(),'--headless','--version'],timeout=30).decode(errors='replace').strip()
        doc=Document();doc.add_paragraph('Office conversion 中文测试');doc.save(root/'sample.docx')
        book=Workbook();book.active['A1']='Office conversion 中文测试';book.save(root/'sample.xlsx')
        deck=Presentation();slide=deck.slides.add_slide(deck.slide_layouts[6]);slide.shapes.add_textbox(Inches(1),Inches(1),Inches(5),Inches(1)).text='Office conversion 中文测试';deck.save(root/'sample.pptx')
        for new,old in [('docx','doc'),('xlsx','xls'),('pptx','ppt')]:
            for source,extension,directory in [(root/('sample.'+new),old,legacy),(legacy/('sample.'+old),new,restored)]:
                subprocess.run([soffice,'-env:UserInstallation='+(root/'profile').as_uri(),'--headless','--convert-to',extension,'--outdir',str(directory),str(source)],check=True,capture_output=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if not (directory/('sample.'+extension)).is_file():raise RuntimeError('Conversion did not produce '+extension)
            report['conversion'][old+'_'+new]='ok'
        font_paths=['C:/Windows/Fonts/msyh.ttc','C:/Windows/Fonts/simhei.ttf','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
        font=ImageFont.truetype(next(p for p in font_paths if Path(p).is_file()),64)
        image=Image.new('RGB',(1400,260),'white');draw=ImageDraw.Draw(image)
        draw.text((35,20),'字数统计环境测试',fill='black',font=font)
        draw.text((35,120),'Word count test 123',fill='black',font=font)
        image.save(root/'scan.png')
        pdf=pymupdf.open();page=pdf.new_page(width=700,height=130);page.insert_image(page.rect,filename=str(root/'scan.png'));pdf.save(root/'scan.pdf');pdf.close()
        pdf=pymupdf.open(root/'scan.pdf');assert not pdf[0].get_text().strip()
        pix=pdf[0].get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False)
        pixels=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
        pdf.close()
        engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
        lines,_=engine(pixels)
        text='\n'.join(line[1] for line in lines or [])
        report['ocr_text']=text
        report['ocr_passed']='字数统计环境测试' in text.replace(' ','') and 'Wordcounttest123' in text.replace(' ','').replace('\n','')
        report['passed']=report['ocr_passed'] and len(report['conversion'])==3
    return report

if __name__=='__main__':
    result=check()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if len(sys.argv)>1:Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if result['passed'] else 1)
