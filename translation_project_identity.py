"""笔译项目以真实文件名作为业务名称，兼容尚未提供文件名的旧接口。"""


def normalize_translation_file_name(value) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("请输入项目名称（真实文件名）")
    if len(name) > 255:
        raise ValueError("项目名称不能超过255个字符")
    return name


def sync_translation_file_name(project, value) -> bool:
    name = normalize_translation_file_name(value)
    changed = project.source_file_name != name or getattr(project, "project_name", None) != name
    project.source_file_name = name
    project.project_name = name
    return changed


def normalize_translation_name_payload(data: dict) -> None:
    if "source_file_name" in data:
        name = normalize_translation_file_name(data["source_file_name"])
        data.update(source_file_name=name, project_name=name)
