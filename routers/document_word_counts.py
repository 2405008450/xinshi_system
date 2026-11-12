"""笔译项目中的本地文件字数统计，不写项目或计费数据。"""
from pathlib import Path
import shutil
import tempfile
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from routers.auth import get_current_user, require_any_permission
import document_word_count_jobs as jobs
from document_word_count_worker import EXTENSIONS

router=APIRouter(prefix='/document-word-count',tags=['document_word_count'],dependencies=[Depends(require_any_permission('projects:read','projects:write'))])

class PathSelection(BaseModel):
    path: str = Field(min_length=1,max_length=2048)
    recursive: bool = True
    relative_paths: list[str] = Field(default_factory=list,max_length=50)
    include_hidden: bool = False
    include_extra: bool = False

@router.post('/discover')
def discover(payload:PathSelection):
    try:return dict(files=jobs.discover(payload.path,payload.recursive))
    except (ValueError,OSError) as exc:raise HTTPException(400,str(exc)) from exc

@router.post('/paths')
def submit_paths(payload:PathSelection,user=Depends(get_current_user)):
    try:
        files=jobs.selected_paths(payload.path,payload.relative_paths)
        return dict(job_id=jobs.submit(user.id,files,payload.include_hidden,payload.include_extra))
    except (ValueError,OSError) as exc:raise HTTPException(400,str(exc)) from exc

@router.post('/upload')
async def upload(files:list[UploadFile]=File(...),include_hidden:bool=Form(False),include_extra:bool=Form(False),user=Depends(get_current_user)):
    if not 1<=len(files)<=jobs.MAX_FILES:raise HTTPException(400,'每批请选择 1 至 50 份文件')
    directory=Path(tempfile.mkdtemp(prefix='xinshi-word-count-')); selected=[];total=0
    try:
        for index,file in enumerate(files):
            name=str(file.filename or '').replace('\\','/').split('/')[-1]
            suffix=Path(name).suffix.lower()
            if suffix not in EXTENSIONS:raise ValueError('不支持的文件类型：'+name)
            path=directory/(str(index)+suffix);size=0
            with path.open('wb') as stream:
                while chunk:=await file.read(1024*1024):
                    size+=len(chunk);total+=len(chunk)
                    if size>jobs.MAX_BYTES or total>jobs.MAX_TOTAL:raise ValueError('单文件限 50 MB，每批合计限 200 MB')
                    stream.write(chunk)
            selected.append((name,path))
        identity=jobs.submit(user.id,selected,include_hidden,include_extra,directory)
        return dict(job_id=identity)
    except ValueError as exc:
        shutil.rmtree(directory,ignore_errors=True)
        raise HTTPException(400,str(exc)) from exc
    except Exception:
        shutil.rmtree(directory,ignore_errors=True)
        raise
    finally:
        for file in files:await file.close()

@router.get('/jobs/{identity}')
def status(identity:str,user=Depends(get_current_user)):
    result=jobs.status(user.id,identity)
    if result is None:raise HTTPException(404,'任务不存在或已过期，请重新统计')
    return result
