"""笔译项目以真实文件名作为业务名称，兼容尚未提供文件名的旧接口。"""


def normalize_translation_file_name(value, *, allow_missing_extension=False) -> str:
    from translation_file_name_rules import normalize_single_file_name
    return normalize_single_file_name(value, allow_missing_extension=allow_missing_extension)


def sync_translation_file_name(project, value) -> bool:
    name = normalize_translation_file_name(value, allow_missing_extension=bool(getattr(project, 'sub_orders', [])))
    changed = project.source_file_name != name or getattr(project, "project_name", None) != name
    project.source_file_name = name
    project.project_name = name
    return changed


def normalize_translation_name_payload(data: dict, *, has_sub_orders=False) -> None:
    if "source_file_name" in data or "project_name" in data:
        name = normalize_translation_file_name(data.get("source_file_name", data.get("project_name")), allow_missing_extension=has_sub_orders)
        data.update(source_file_name=name, project_name=name)
