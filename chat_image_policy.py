"""聊天图片按体积处理；阈值内保留上传的原始字节。"""
from collections import OrderedDict
from io import BytesIO
from threading import Lock

from PIL import Image, ImageOps, UnidentifiedImageError

ORIGINAL_MAX_BYTES = 10 * 1024 * 1024
UPLOAD_MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
THUMBNAIL_MAX_EDGE = 480
THUMBNAIL_MIN_SOURCE_BYTES = 32 * 1024
THUMBNAIL_CACHE_MAX_ITEMS = 256
IMAGE_TYPES = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif', 'WEBP': 'image/webp'}

_THUMBNAIL_CACHE: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
_THUMBNAIL_CACHE_LOCK = Lock()


def normalize_chat_image(content: bytes, content_type: str) -> tuple[bytes, str]:
    if not content:
        raise ValueError('图片内容为空')
    if len(content) > UPLOAD_MAX_BYTES:
        raise ValueError('单张聊天图片不能超过 20MB')
    try:
        with Image.open(BytesIO(content)) as source:
            mime = IMAGE_TYPES.get(source.format)
            if not mime or mime != content_type:
                raise ValueError('图片格式与文件内容不匹配')
            if source.width * source.height > MAX_PIXELS:
                raise ValueError('图片像素尺寸过大，请裁剪后重试')
            source.verify()
        with Image.open(BytesIO(content)) as source:
            animated = getattr(source, 'is_animated', False)
            if animated and len(content) > ORIGINAL_MAX_BYTES:
                raise ValueError('动图超过 10MB，请缩小文件后重试；系统不会将动图转为静态图')
            # 解码每一帧，避免只验证文件头而保存截断的图片。
            for frame in range(getattr(source, 'n_frames', 1)):
                source.seek(frame)
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError('图片像素尺寸过大，请裁剪后重试')
                source.load()
            if len(content) <= ORIGINAL_MAX_BYTES:
                return content, mime
            source.seek(0)
            image = ImageOps.exif_transpose(source)
            alpha = 'A' in image.getbands() or 'transparency' in image.info
            image = image.convert('RGBA' if alpha else 'RGB')
            for settings in ({'lossless': True}, {'quality': 95}, {'quality': 90}, {'quality': 85}):
                output = BytesIO()
                image.save(output, 'WEBP', **settings)
                if output.tell() <= ORIGINAL_MAX_BYTES:
                    return output.getvalue(), 'image/webp'
            raise ValueError('图片适度压缩后仍超过 10MB，请裁剪或更换图片')
    except (UnidentifiedImageError, OSError, EOFError, Image.DecompressionBombError) as error:
        raise ValueError('图片内容无效或无法完整解码') from error


def make_chat_thumbnail(content: bytes, content_type: str, *, cache_key: str | None = None) -> tuple[bytes, str]:
    """生成聊天气泡预览用 WebP 缩略图；小图、动图、非图片或转换无收益时返回原字节。"""
    if not content or not content_type or not content_type.startswith('image/'):
        return content, content_type
    if len(content) <= THUMBNAIL_MIN_SOURCE_BYTES:
        return content, content_type
    if cache_key:
        with _THUMBNAIL_CACHE_LOCK:
            cached = _THUMBNAIL_CACHE.get(cache_key)
            if cached is not None:
                _THUMBNAIL_CACHE.move_to_end(cache_key)
                return cached
    result = (content, content_type)
    try:
        with Image.open(BytesIO(content)) as source:
            if getattr(source, 'is_animated', False):
                result = (content, content_type)
            else:
                image = ImageOps.exif_transpose(source)
                if max(image.width, image.height) > THUMBNAIL_MAX_EDGE:
                    image.thumbnail((THUMBNAIL_MAX_EDGE, THUMBNAIL_MAX_EDGE), Image.Resampling.LANCZOS)
                alpha = 'A' in image.getbands() or 'transparency' in image.info
                image = image.convert('RGBA' if alpha else 'RGB')
                output = BytesIO()
                image.save(output, 'WEBP', quality=75, method=4)
                thumb_bytes = output.getvalue()
                if thumb_bytes and len(thumb_bytes) < len(content):
                    result = (thumb_bytes, 'image/webp')
    except (UnidentifiedImageError, OSError, EOFError, Image.DecompressionBombError):
        result = (content, content_type)
    if cache_key:
        with _THUMBNAIL_CACHE_LOCK:
            _THUMBNAIL_CACHE[cache_key] = result
            _THUMBNAIL_CACHE.move_to_end(cache_key)
            while len(_THUMBNAIL_CACHE) > THUMBNAIL_CACHE_MAX_ITEMS:
                _THUMBNAIL_CACHE.popitem(last=False)
    return result
