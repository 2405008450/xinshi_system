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
