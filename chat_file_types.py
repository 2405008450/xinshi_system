"""沟通附件格式、限额及音视频容器校验。"""
from fastapi import HTTPException

FILE_TYPES = {'.pdf': 'application/pdf', '.txt': 'text/plain', '.csv': 'text/csv', '.zip': 'application/zip',
    '.doc': 'application/msword', '.xls': 'application/vnd.ms-excel', '.ppt': 'application/vnd.ms-powerpoint',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'}
MEDIA_TYPES = {'.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
               '.m4a': 'audio/mp4', '.webm': 'video/webm'}
FILE_TYPES.update(MEDIA_TYPES)
MEDIA_MAX_BYTES = 100 * 1024 * 1024
FILE_HINT = '支持图片、PDF、Office、TXT、CSV、ZIP及MP4、MP3、WAV、M4A、WebM；图片最多10MB，音视频最多100MB，其他文件最多20MB'


def validate_media(suffix, content):
    if suffix not in MEDIA_TYPES:
        return
    valid = False
    if suffix in {'.mp4', '.m4a'}:
        # ISO BMFF 必须有完整 ftyp 盒，不能只靠扩展名或 MIME 判断。
        size = int.from_bytes(content[:4], 'big')
        if len(content) >= 16 and content[4:8] == b'ftyp' and 16 <= size <= min(len(content), 4096) and size % 4 == 0:
            brands = {content[8:12], *(content[i:i+4] for i in range(16, size, 4))}
            allowed = {b'isom', b'iso2', b'iso5', b'iso6', b'mp41', b'mp42', b'avc1', b'M4V ', b'M4A ', b'M4B ', b'dash'}
            valid = bool(brands & allowed) and (suffix != '.m4a' or bool(brands & {b'M4A ', b'M4B ', b'isom', b'mp42'}))
    elif suffix == '.wav':
        valid = len(content) >= 44 and content[:4] == b'RIFF' and content[8:12] == b'WAVE' and b'fmt ' in content[12:4096]
    elif suffix == '.webm':
        valid = content.startswith(b'\x1a\x45\xdf\xa3') and b'\x42\x82\x84webm' in content[:4096]
    elif suffix == '.mp3':
        offset = 0
        if content.startswith(b'ID3') and len(content) >= 10:
            sizes = content[6:10]
            if any(v & 0x80 for v in sizes):
                raise HTTPException(415, 'MP3标签格式无效')
            offset = 10 + sum(v << shift for v, shift in zip(sizes, (21, 14, 7, 0)))
            if content[5] & 0x10:
                offset += 10
        header = content[offset:offset+4]
        valid = len(header) == 4 and header[0] == 255 and header[1] & 0xe0 == 0xe0 and header[1] & 0x18 != 0x08 and header[1] & 0x06 == 0x02 and header[2] >> 4 not in (0, 15) and header[2] & 0x0c != 0x0c
    if not valid:
        raise HTTPException(415, '音视频格式与内容不匹配或文件头无效')
