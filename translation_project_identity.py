"""笔译项目以真实文件名作为业务名称，兼容尚未提供文件名的旧接口。"""


def normalize_translation_file_name(value) -> str:
    from translation_file_name_rules import normalize_single_file_name
    return normalize_single_file_name(value)


def sync_translation_file_name(project, value) -> bool:
    name = normalize_translation_file_name(value)
    changed = project.source_file_name != name or getattr(project, "project_name", None) != name
    project.source_file_name = name
    project.project_name = name
    return changed


def normalize_translation_name_payload(data: dict) -> None:
    if "source_file_name" in data or "project_name" in data:
        name = normalize_translation_file_name(data.get("source_file_name", data.get("project_name")))
        data.update(source_file_name=name, project_name=name)
