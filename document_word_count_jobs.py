"""本机文件统计任务；结果按用户隔离，临时上传文件用后删除。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PureWindowsPath
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from uuid import uuid4
from document_word_count_worker import EXTENSIONS, POLICY
from path_security import validate_managed_path

MAX_FILES = 50
MAX_BYTES = 50*1024*1024
MAX_TOTAL = 200*1024*1024
_pool = ThreadPoolExecutor(max_workers=2,thread_name_prefix='file-word-count')
_lock = threading.Lock()
_jobs = {}

def managed_root(value):
    normalized = validate_managed_path(value)
    if not normalized or not normalized.startswith('\\\\'):
        raise ValueError('请输入允许访问的 UNC 共享路径，例如 \\\\Win-server\\共享目录')
    return Path(normalized)

def validate_components(path, root):
    from project_file_service import _is_reparse_point
    current = path
    while True:
        if current.is_symlink() or _is_reparse_point(current):
            raise ValueError('不能读取符号链接或目录联接')
        if current == root:break
        if current == current.parent:raise ValueError('文件超出共享目录')
        current = current.parent

def discover(value, recursive=True):
    root = managed_root(value)
    validate_components(root, Path(root.anchor))
    if root.is_file():
        if root.suffix.lower() not in EXTENSIONS:raise ValueError('不支持该文件类型')
        return [dict(relative_path=root.name,size=root.stat().st_size)]
    if not root.is_dir():raise ValueError('共享目录不存在或当前登录会话无权访问')
    results=[];folders=0;entries=0
    for folder, directories, files in os.walk(root,followlinks=False):
        folders+=1;entries+=len(files)+len(directories)
        if folders>5000 or entries>20000 or len(Path(folder).relative_to(root).parts)>20:raise ValueError("目录范围过大，请选择更具体的共享文件夹")
        validate_components(Path(folder),root)
        for name in directories:
            validate_components(Path(folder)/name,root)
        if not recursive:directories[:]=[]
        for name in sorted(files,key=str.casefold):
            path=Path(folder)/name
            if name.startswith('~$') or path.suffix.lower() not in EXTENSIONS:continue
            validate_components(path,root)
            results.append(dict(relative_path=path.relative_to(root).as_posix(),size=path.stat().st_size))
            if len(results)>2000:raise ValueError('目录超过 2000 份文件，请选择更具体的共享目录')
    return results

def selected_paths(value, relative_paths):
    root=managed_root(value)
    validate_components(root,Path(root.anchor))
    if not relative_paths or len(relative_paths)>MAX_FILES:raise ValueError('每批请选择 1 至 50 份文件')
    result=[];seen=set();total=0
    for relative in relative_paths:
        win=PureWindowsPath(relative)
        if win.is_absolute() or win.drive or any(part in {'.','..'} for part in win.parts):raise ValueError('无效的相对文件路径')
        if root.is_file():
            if relative != root.name:raise ValueError('文件选择与共享路径不一致')
            path=root
        else:path=root.joinpath(*win.parts)
        key=str(path).casefold()
        if key in seen:continue
        seen.add(key)
        validate_components(path,root if root.is_dir() else root.parent)
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:raise ValueError('所选文件不存在或格式不支持')
        size=path.stat().st_size
        if size>MAX_BYTES:raise ValueError('单个文件不能超过 50 MB')
        total+=size
        if total>MAX_TOTAL:raise ValueError('每批文件总大小不能超过 200 MB')
        result.append((relative,path))
    return result

def submit(owner, files, include_hidden=False, include_extra=False, temporary=None):
    now=time.monotonic()
    with _lock:
        for key in list(_jobs):
            if _jobs[key]['status'] in {'completed','failed'} and now-_jobs[key]['touched']>3600:del _jobs[key]
        if sum(j['status'] in {'queued','running'} for j in _jobs.values())>=16:raise ValueError('统计任务较多，请稍后重试')
        if sum(j['owner']==str(owner) and j['status'] in {'queued','running'} for j in _jobs.values())>=3:raise ValueError('最多同时提交 3 个统计任务')
        identity=uuid4().hex
        _jobs[identity]=dict(owner=str(owner),status='queued',total=len(files),completed=0,files=[],touched=now,policy=POLICY,include_hidden=include_hidden,include_extra=include_extra)
    _pool.submit(_execute,identity,files,include_hidden,include_extra,temporary)
    return identity

def _execute(identity, files, hidden, extra, temporary):
    with _lock:_jobs[identity]['status']='running'
    try:
        for name,path in files:
            try:
                process=subprocess.run([sys.executable,str(Path(__file__).with_name('document_word_count_worker.py')),str(path),'1' if hidden else '0','1' if extra else '0'],
                    capture_output=True,timeout=90,env={**os.environ,'PYTHONIOENCODING':'utf-8'},creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if process.returncode:raise ValueError('文件解析进程失败')
                row=json.loads(process.stdout.decode('utf-8'))
            except subprocess.TimeoutExpired:row=dict(status='failed',words=None,message='文件统计超过 90 秒，请拆分或转换后重试')
            except Exception as exc:row=dict(status='failed',words=None,message=str(exc))
            row['name']=name
            with _lock:
                _jobs[identity]['files'].append(row);_jobs[identity]['completed']+=1
        with _lock:_jobs[identity]['status']='completed'
    except Exception:
        with _lock:_jobs[identity]['status']='failed'
    finally:
        if temporary:shutil.rmtree(temporary,ignore_errors=True)
        with _lock:_jobs[identity]['touched']=time.monotonic()

def status(owner, identity):
    with _lock:
        job=_jobs.get(identity)
        if not job or job['owner']!=str(owner):return None
        result={key:value for key,value in job.items() if key not in {'owner','touched'}}
        result['files']=[dict(row) for row in job['files']]
    good=[r for r in result['files'] if r['status']=='counted']
    result['words']=sum(r['words'] for r in good)
    result['characters_no_spaces']=sum(r.get('characters_no_spaces',0) for r in good)
    result['counted_files']=len(good)
    result['failed_files']=sum(r['status']!='counted' for r in result['files'])
    return result
