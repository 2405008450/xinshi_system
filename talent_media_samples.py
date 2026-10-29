"""口译、标注样音支持的音视频格式；原样保存，不进行转码。"""
AUDIO_EXTENSIONS = {'.mp3','.mp2','.wav','.m4a','.aac','.ogg','.oga','.opus','.flac','.aif','.aiff','.wma','.amr','.ape','.mid','.midi','.caf','.au','.snd','.mka','.ac3','.dts','.wv'}
VIDEO_EXTENSIONS = {'.mp4','.mov','.m4v','.webm','.mkv','.avi','.wmv','.mpeg','.mpg','.3gp','.3g2','.ts','.mts','.m2ts','.vob','.flv','.ogv','.rm','.rmvb','.asf','.f4v','.divx','.m2v'}
SAMPLE_CATEGORIES = {'interpretation_sample', 'annotation_sample'}
MAX_SAMPLE_BYTES = 200 * 1024 * 1024


def sample_content_type(extension):
    import mimetypes
    value = {'.mp3':'audio/mpeg','.wav':'audio/wav','.m4a':'audio/mp4','.flac':'audio/flac',
            '.mp4':'video/mp4','.mov':'video/quicktime','.m4v':'video/mp4','.webm':'video/webm',
            '.mkv':'video/x-matroska','.avi':'video/x-msvideo','.wmv':'video/x-ms-wmv', '.ts':'video/mp2t','.mts':'video/mp2t','.m2ts':'video/mp2t'}.get(extension) or mimetypes.guess_type('sample'+extension)[0]
    return value if value and value.startswith(('audio/', 'video/')) else 'application/octet-stream'
