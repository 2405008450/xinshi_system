"""纯图片处理测试，不连接数据库。"""
from io import BytesIO
import pytest
from PIL import Image
import chat_image_policy as policy


def picture(fmt='PNG', animated=False):
    output = BytesIO()
    image = Image.new('RGBA' if fmt in {'PNG', 'WEBP'} else 'RGB', (2400, 32), (20, 40, 60))
    options = {}
    if animated:
        options = dict(save_all=True, append_images=[Image.new('RGB', image.size, 'red')], duration=100, loop=0)
    image.save(output, fmt, **options)
    return output.getvalue()


@pytest.mark.parametrize('fmt', ['PNG', 'JPEG', 'GIF', 'WEBP'])
def test_original_bytes_and_large_dimensions_preserved(fmt):
    content = picture(fmt)
    assert policy.normalize_chat_image(content, policy.IMAGE_TYPES[fmt]) == (content, policy.IMAGE_TYPES[fmt])


@pytest.mark.parametrize('fmt', ['GIF', 'WEBP', 'PNG'])
def test_animation_preserved_and_oversized_animation_rejected(fmt, monkeypatch):
    content = picture(fmt, animated=True)
    assert policy.normalize_chat_image(content, policy.IMAGE_TYPES[fmt])[0] == content
    monkeypatch.setattr(policy, 'ORIGINAL_MAX_BYTES', len(content)-1)
    with pytest.raises(ValueError, match='动图超过'):
        policy.normalize_chat_image(content, policy.IMAGE_TYPES[fmt])


def test_real_size_boundaries_and_lossless_compression():
    content = picture()
    at_limit = content + b'\0' * (policy.ORIGINAL_MAX_BYTES - len(content))
    assert policy.normalize_chat_image(at_limit, 'image/png')[0] == at_limit
    for size in (policy.ORIGINAL_MAX_BYTES + 1, policy.UPLOAD_MAX_BYTES):
        data, mime = policy.normalize_chat_image(content + b'\0' * (size-len(content)), 'image/png')
        assert mime == 'image/webp' and len(data) <= policy.ORIGINAL_MAX_BYTES
        with Image.open(BytesIO(data)) as result, Image.open(BytesIO(content)) as original:
            assert result.size == original.size
            assert result.convert('RGBA').tobytes() == original.convert('RGBA').tobytes()
    with pytest.raises(ValueError, match='20MB'):
        policy.normalize_chat_image(b'0' * (policy.UPLOAD_MAX_BYTES + 1), 'image/png')


def test_quality_floor_and_no_resize(monkeypatch):
    content = picture()
    monkeypatch.setattr(policy, 'ORIGINAL_MAX_BYTES', 1)
    calls = []
    def encode(self, output, fmt, **options):
        calls.append((self.size, options))
        output.write(b'xx')
    monkeypatch.setattr(Image.Image, 'save', encode)
    with pytest.raises(ValueError, match='适度压缩后仍超过'):
        policy.normalize_chat_image(content, 'image/png')
    assert calls == [((2400, 32), settings) for settings in ({'lossless': True}, {'quality': 95}, {'quality': 90}, {'quality': 85})]


def test_invalid_images_and_pixel_limit(monkeypatch):
    for data, mime in [(b'', 'image/png'), (b'bad', 'image/png'), (picture(), 'image/jpeg'), (picture()[:60], 'image/png')]:
        with pytest.raises(ValueError):
            policy.normalize_chat_image(data, mime)
    monkeypatch.setattr(policy, 'MAX_PIXELS', 10)
    with pytest.raises(ValueError, match='像素'):
        policy.normalize_chat_image(picture(), 'image/png')
