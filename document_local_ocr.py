"""独立本地 OCR；固定 PaddleOCR v5 mobile，可显式切换为 RapidOCR。"""
import importlib.util
import os
from pathlib import Path
import tempfile

IMAGE_EXTENSIONS={'.png','.jpg','.jpeg','.bmp','.tif','.tiff','.webp'}
MAX_PAGES=30
_engine=None
_modern=False
_engine_name=None

def _get_engine():
    global _engine,_modern,_engine_name
    if _engine is None:
        try:
            selected=os.getenv('WORD_COUNT_OCR_ENGINE','paddleocr').strip().lower()
            if selected not in {'paddleocr','rapidocr'}:
                raise ValueError('WORD_COUNT_OCR_ENGINE 仅支持 paddleocr 或 rapidocr')
            if selected=='paddleocr':
                from paddleocr import PaddleOCR
                _engine=PaddleOCR(device='cpu',text_detection_model_name='PP-OCRv5_mobile_det',
                    text_recognition_model_name='PP-OCRv5_mobile_rec',use_doc_orientation_classify=False,
                    use_doc_unwarping=False,use_textline_orientation=False,cpu_threads=2,enable_mkldnn=False)
                _engine_name='PaddleOCR/PP-OCRv5_mobile'
            elif importlib.util.find_spec('rapidocr_onnxruntime'):
                from rapidocr_onnxruntime import RapidOCR
                _engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
            else:
                from rapidocr import RapidOCR
                _modern=True
                _engine=RapidOCR(params={'EngineConfig.onnxruntime.intra_op_num_threads':2,'EngineConfig.onnxruntime.inter_op_num_threads':2})
            if selected=='rapidocr':_engine_name='RapidOCR/ONNX'
        except Exception as exc:
            raise RuntimeError('本地 OCR 初始化失败，请检查所选引擎的依赖和模型：'+str(exc)) from exc
    return _engine

def recognize_image(image):
    import numpy as np
    from PIL import ImageOps
    if image.width*image.height>40_000_000:raise ValueError('图片超过 4000 万像素，请缩小后重试')
    image=ImageOps.exif_transpose(image).convert('RGB')
    image.thumbnail((2400,2400))
    engine=_get_engine()
    if _engine_name=='PaddleOCR/PP-OCRv5_mobile':
        import json
        texts=[];scores=[]
        for result in engine.predict(np.asarray(image)):
            value=result.json
            if isinstance(value,str):value=json.loads(value)
            value=value.get('res',value)
            texts.extend(value.get('rec_texts',[]));scores.extend(float(score) for score in value.get('rec_scores',[]))
        return '\n'.join(str(text) for text in texts if str(text).strip()),scores
    # 两个 RapidOCR 版本都接收 BGR 数组。
    result=engine(np.asarray(image)[:,:,::-1].copy())
    if _modern:
        texts=list(result.txts or []);scores=list(result.scores or [])
    else:
        rows=result[0] or [];texts=[row[1] for row in rows];scores=[row[2] for row in rows]
    return '\n'.join(str(text) for text in texts if str(text).strip()), scores

def extract(path):
    from PIL import Image
    path=Path(path);texts=[];scores=[];ocr_pages=[]
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        with Image.open(path) as image:
            total=getattr(image,'n_frames',1)
            if total>MAX_PAGES:raise ValueError('单文件 OCR 最多 30 页，请拆分后统计')
            for index in range(total):
                image.seek(index);text,page_scores=recognize_image(image.copy())
                if not text.strip():raise ValueError(f'第 {index+1} 页未识别到文字，请核验是否空白或识别遗漏')
                texts.append(text);scores.extend(page_scores);ocr_pages.append(index+1)
    else:
        import pymupdf
        with pymupdf.open(path) as document:
            total=len(document)
            if total>MAX_PAGES:raise ValueError('单文件 OCR 最多 30 页，请拆分后统计')
            for index,page in enumerate(document):
                native=page.get_text().strip()
                image_area=sum(pymupdf.Rect(info['bbox']).get_area() for info in page.get_image_info())
                scanned=image_area>=page.rect.get_area()*.5 and len(native)<40
                if native and not scanned:
                    texts.append(native);continue
                if not page.get_images() and not page.get_drawings():
                    texts.append('');continue
                scale=min(200/72,2400/max(page.rect.width,page.rect.height))
                pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False,colorspace=pymupdf.csRGB)
                image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                text,page_scores=recognize_image(image)
                if not text.strip():raise ValueError(f'第 {index+1} 页未识别到文字，请核验扫描内容')
                texts.append(text);scores.extend(page_scores);ocr_pages.append(index+1)
    text='\n\n'.join(texts)
    if len(text)>200_000:raise ValueError('识别文本超过 20 万字符，请拆分后统计')
    return dict(text=text,pages=total,ocr_pages=ocr_pages,ocr_used=bool(ocr_pages),
                ocr_engine=_engine_name or '本地 OCR',review_required=bool(ocr_pages),
                low_confidence=any(score<.6 for score in scores))
