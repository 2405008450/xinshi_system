"""只读盘点沟通附件，输出迁移所需的文件哈希及数据库记录，不输出凭据。"""
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import engine
from sqlalchemy import text


def inventory():
    directory = Path(os.getenv('CHAT_UPLOAD_DIR', 'data/chat_uploads')).resolve()
    files = {}
    if directory.exists():
        for path in directory.iterdir():
            if path.is_file():
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                files[path.name] = {'size': path.stat().st_size, 'sha256': digest.hexdigest()}
    with engine.connect() as connection:
        rows = connection.execute(text('SELECT id, storage_name, file_size FROM chat_project_attachment')).mappings()
        attachments = [{'id': str(row['id']), 'storage_name': row['storage_name'], 'file_size': row['file_size']} for row in rows]
    return {'directory': str(directory), 'files': files, 'attachments': attachments}


if __name__ == '__main__':
    print(json.dumps(inventory(), ensure_ascii=True))
