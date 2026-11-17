import io
import time
from types import SimpleNamespace
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from docx import Document
from openpyxl import Workbook
import pytest
import document_word_count_jobs as jobs
from document_word_count_worker import count_file
from routers.document_word_counts import router
from routers.auth import get_current_user


def test_docx_core_matches_validated_rules(tmp_path):
    doc=Document();doc.add_paragraph('中文，标点。');doc.add_paragraph('Visit https://example.com/a?x=1&y=2')
    path=tmp_path/'sample.docx';doc.save(path)
    result=count_file(path)
    assert result['words']==8


def test_excel_hidden_scope(tmp_path):
    book=Workbook();sheet=book.active
    sheet['A1']='正文';sheet['B1']='隐藏列';sheet['C1']='同组隐藏列'
    sheet.column_dimensions.group('B','C',hidden=True)
    path=tmp_path/'sample.xlsx';book.save(path)
    assert count_file(path)['words']==2
    result=count_file(path,True)
    assert result['words']==10 and result['hidden_words']==8


def test_image_only_docx_is_not_zero_word_pass(tmp_path):
    doc=Document();path=tmp_path/'empty.docx';doc.save(path)
    assert count_file(path)['status']=='needs_ocr'


def test_shared_path_security():
    with pytest.raises(ValueError):jobs.managed_root('C:/Windows')
    with pytest.raises(ValueError):jobs.managed_root('\\\\unknown\\share\\..\\secret')


def test_selection_traversal_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(jobs,'managed_root',lambda _:tmp_path)
    with pytest.raises(ValueError):jobs.selected_paths('share',['../secret.txt'])


def test_async_upload_and_owner_isolation(tmp_path):
    app=FastAPI();app.include_router(router)
    for dependency in router.dependencies:app.dependency_overrides[dependency.dependency]=lambda:None
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id='user-a')
    # 只挂载无数据库的统计路由，不导入主应用、不调用业务写入。
    with TestClient(app) as client:
        response=client.post('/document-word-count/upload',files=[('files',('test.txt','Привет мир'.encode()))])
        assert response.status_code==200,response.text
        identity=response.json()['job_id']
        for _ in range(100):
            result=client.get('/document-word-count/jobs/'+identity).json()
            if result['status']=='completed':break
            time.sleep(.1)
        assert result['words']==2 and result['counted_files']==1
        app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id='user-b')
        assert client.get('/document-word-count/jobs/'+identity).status_code==404
        assert client.post('/document-word-count/upload',files=[('files',('danger.exe',b'x'))]).status_code==400


def test_statistics_routes_require_authentication():
    app=FastAPI();app.include_router(router)
    with TestClient(app) as client:
        assert client.get('/document-word-count/jobs/unknown').status_code in {401,403}


def test_all_four_metrics_have_distinct_values(tmp_path):
    text='中文，한국어 hello Привет 123'
    path=tmp_path/'mixed.txt';path.write_text(text,encoding='utf-8')
    result=count_file(path)
    assert result['words']==9
    assert result['characters_no_spaces']==len('中文，한국어helloПривет123')
    assert result['cjk_chars_korean_words']==6
    assert result['foreign_words']==2
    assert result['characters_with_spaces']==len(text)


def test_extra_scope_applies_to_every_metric(tmp_path):
    doc=Document();doc.add_paragraph('正文');doc.sections[0].header.paragraphs[0].text='extra'
    path=tmp_path/'header.docx';doc.save(path)
    main=count_file(path);combined=count_file(path,include_extra=True)
    assert main['words']==2 and combined['words']==3
    assert main['foreign_words']==0 and combined['foreign_words']==1
    assert main['cjk_chars_korean_words']==combined['cjk_chars_korean_words']==2
    assert combined['characters_no_spaces']-main['characters_no_spaces']==5


def test_task_sums_metrics_without_using_words_for_other_fields(monkeypatch):
    records=[dict(status='counted',words=4,characters_no_spaces=20,cjk_chars_korean_words=2,foreign_words=1,characters_with_spaces=24),
             dict(status='counted',words=7,characters_no_spaces=30,cjk_chars_korean_words=5,foreign_words=2,characters_with_spaces=35)]
    monkeypatch.setitem(jobs._jobs,'four-metrics',dict(owner='qa',status='completed',files=records,touched=0))
    result=jobs.status('qa','four-metrics')
    assert [result[key] for key in ['words','characters_no_spaces','cjk_chars_korean_words','foreign_words']]==[11,50,7,3]
    records[0].pop('foreign_words')
    assert jobs.status('qa','four-metrics')['foreign_words'] is None


def test_image_worker_outputs_clean_json(tmp_path):
    import subprocess,sys,json
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(900,150),'white')
    ImageDraw.Draw(image).text((20,30),'Word count test 123',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48),fill='black')
    path=tmp_path/'scan.png';image.save(path)
    process=subprocess.run([sys.executable,str(Path(__file__).parents[1]/'document_word_count_worker.py'),str(path),'0','0'],capture_output=True,timeout=120,env={**__import__('os').environ,'PYTHONIOENCODING':'utf-8'})
    result=json.loads(process.stdout.decode('utf-8'))
    assert result['status']=='counted',result
    assert result['ocr_used'] and result['review_required']
    assert 'Word' in result['ocr_text'] and '123' in result['ocr_text']
    from document_word_count_worker import text_statistics
    expected=text_statistics(result['ocr_text'])
    assert all(result[key]==value for key,value in expected.items())


def test_pdf_combines_native_and_scanned_pages_without_duplication(tmp_path,monkeypatch):
    import pymupdf
    from PIL import Image
    import document_local_ocr
    image=tmp_path/'scan.png';Image.new('RGB',(200,100),'white').save(image)
    path=tmp_path/'mixed.pdf';document=pymupdf.open();document.new_page().insert_text((50,50),'Native page text')
    page=document.new_page();page.insert_image(page.rect,filename=str(image));document.save(path);document.close()
    monkeypatch.setattr(document_local_ocr,'recognize_image',lambda _:('中文 OCR text',[.99]))
    result=count_file(path)
    assert result['words']==7 and result['ocr_pages']==[2]
    assert result['ocr_text'].count('Native page text')==1


def test_unc_discovery_and_selected_paths_include_images(tmp_path,monkeypatch):
    from PIL import Image
    Image.new('RGB',(100,50),'white').save(tmp_path/'scan.jpg')
    monkeypatch.setattr(jobs,'managed_root',lambda _:tmp_path)
    assert jobs.discover('share')[0]['relative_path']=='scan.jpg'
    assert jobs.selected_paths('share',['scan.jpg'])[0][1]==tmp_path/'scan.jpg'


def test_image_upload_reaches_ocr_and_returns_all_metrics():
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(900,150),'white')
    ImageDraw.Draw(image).text((20,30),'Word count test 123',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',48),fill='black')
    payload=io.BytesIO();image.save(payload,format='PNG')
    app=FastAPI();app.include_router(router)
    for dependency in router.dependencies:app.dependency_overrides[dependency.dependency]=lambda:None
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id='image-user')
    with TestClient(app) as client:
        response=client.post('/document-word-count/upload',files=[('files',('scan.png',payload.getvalue(),'image/png'))])
        assert response.status_code==200,response.text
        identity=response.json()['job_id']
        for _ in range(150):
            result=client.get('/document-word-count/jobs/'+identity).json()
            if result['status']=='completed':break
            time.sleep(.1)
        assert result['counted_files']==1 and result['failed_files']==0,result
        row=result['files'][0]
        assert row['ocr_used'] and row['ocr_text'] and row['review_required']
        for key in ['words','characters_no_spaces','cjk_chars_korean_words','foreign_words']:
            assert result[key]==row[key]
