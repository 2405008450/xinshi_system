"""聊天图片按体积处理；阈值内保留上传的原始字节。"""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ORIGINAL_MAX_BYTES = 10 * 1024 * 1024
UPLOAD_MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
IMAGE_TYPES = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'GIF': 'image/gif', 'WEBP': 'image/webp'}


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
