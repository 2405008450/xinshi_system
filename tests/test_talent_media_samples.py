import asyncio
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from talent_attachment_service import UPLOAD_RULES, save_talent_attachment
from talent_media_samples import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, MAX_SAMPLE_BYTES


@pytest.mark.parametrize('extension',['.mp3','.wav','.flac','.wma','.amr','.mp4','.mov','.mkv','.avi','.wmv','.rmvb'])
@pytest.mark.parametrize('category',['interpretation_sample','annotation_sample'])
def test_sample_formats_registered_without_changing_legacy_upload_rules(extension,category):
    assert extension in UPLOAD_RULES[category][0]
    assert UPLOAD_RULES[category][1]==MAX_SAMPLE_BYTES
    assert UPLOAD_RULES['photo'][1]==10*1024*1024


@pytest.fixture
def sample_store(monkeypatch,tmp_path):
    import main  # 注册 ORM 关系，不启动服务、不连接业务库。
    monkeypatch.setenv('TALENT_UPLOAD_DIR',str(tmp_path))
    monkeypatch.setattr('resource_service.get_talent',lambda *_:SimpleNamespace(id=uuid4()))
    monkeypatch.setattr('talent_duplicate_service.assert_writable',lambda *_:None)
    monkeypatch.setattr('talent_wechat_accounts.lock_account_writes',lambda *_:None)
    query=SimpleNamespace(filter=lambda *_:query,first=lambda:SimpleNamespace(id=uuid4()),count=lambda:0)
    records=[]
    db=SimpleNamespace(query=lambda *_:query,add=lambda row:records.append(row),commit=lambda:None,rollback=lambda:None,refresh=lambda *_:None)
    return db,records,tmp_path


def test_sample_upload_uses_safe_media_type_and_preserves_bytes(sample_store):
    db,records,directory=sample_store
    upload=UploadFile(filename='样音.MKV',file=BytesIO(b'isolated-media-bytes'),headers=Headers({'content-type':'text/html'}))
    result=asyncio.run(save_talent_attachment(db,uuid4(),'interpretation_sample',upload,uploaded_by=uuid4()))
    assert result.content_type=='video/x-matroska'
    assert result.category=='interpretation_sample'
    assert (directory/result.storage_name).read_bytes()==b'isolated-media-bytes'


@pytest.mark.parametrize('name,content',[('bad.exe',b'not-media'),('empty.mp3',b'')])
def test_invalid_sample_does_not_leave_file_or_record(sample_store,name,content):
    db,records,directory=sample_store
    with pytest.raises(ValueError):
        asyncio.run(save_talent_attachment(db,uuid4(),'annotation_sample',UploadFile(filename=name,file=BytesIO(content)),uploaded_by=uuid4()))
    assert records==[] and list(directory.iterdir())==[]


@pytest.mark.parametrize('category',['id_photo','life_photo','photo'])
def test_photo_categories_are_saved_separately_and_preserve_legacy(sample_store,category):
    db,records,directory=sample_store
    assert UPLOAD_RULES[category]==({'.jpg','.jpeg','.png','.webp'},10*1024*1024)
    result=asyncio.run(save_talent_attachment(db,uuid4(),category,UploadFile(filename='portrait.PNG',file=BytesIO(b'photo-content')),uploaded_by=uuid4()))
    assert result.category==category
    assert (directory/result.storage_name).read_bytes()==b'photo-content'


@pytest.mark.parametrize('category',['id_photo','life_photo'])
def test_photo_categories_reject_video(sample_store,category):
    db,records,directory=sample_store
    with pytest.raises(ValueError,match='不支持的文件格式'):
        asyncio.run(save_talent_attachment(db,uuid4(),category,UploadFile(filename='sample.mp4',file=BytesIO(b'video')),uploaded_by=uuid4()))
    assert records==[] and list(directory.iterdir())==[]
