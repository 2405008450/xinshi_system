from types import SimpleNamespace

from crud import _attach_project_client_fields


def test_translation_project_response_keeps_parent_and_sub_client_separate():
    parent = SimpleNamespace(
        client_name="母客户全称",
        client_short_name="母客户",
        client_code="CL-001",
        client_manager="母客户经理",
        manager_contact="parent@example.com",
    )
    sub_client = SimpleNamespace(
        client_name="子客户全称",
        client_short_name="子客户",
        sub_client_code="CL-001.001",
        client_manager="子客户经理",
        manager_contact="sub@example.com",
    )
    project = SimpleNamespace(client=parent, sub_client=sub_client)

    _attach_project_client_fields(project)

    assert project.client_name == "母客户全称"
    assert project.client_short_name == "母客户"
    assert project.client_code == "CL-001"
    assert project.client_manager == "母客户经理"
    assert project.manager_contact == "parent@example.com"
    assert project.sub_client_name == "子客户全称"
    assert project.sub_client_short_name == "子客户"
    assert project.sub_client_code == "CL-001.001"


def test_translation_project_response_allows_parent_without_sub_client():
    parent = SimpleNamespace(
        client_name="母客户全称",
        client_short_name="母客户",
        client_code="CL-001",
        client_manager=None,
        manager_contact=None,
    )
    project = SimpleNamespace(client=parent, sub_client=None)

    _attach_project_client_fields(project)

    assert project.client_short_name == "母客户"
    assert project.sub_client_name is None
    assert project.sub_client_short_name is None
    assert project.sub_client_code is None


def test_translation_project_response_falls_back_to_sub_client_short_name():
    parent = SimpleNamespace(
        client_name="Parent full name",
        client_short_name="Parent",
        client_code="CL-001",
        client_manager=None,
        manager_contact=None,
    )
    sub_client = SimpleNamespace(
        client_name="",
        client_short_name="Child",
        sub_client_code="CL-001.001",
    )
    project = SimpleNamespace(client=parent, sub_client=sub_client)

    _attach_project_client_fields(project)

    assert project.sub_client_name == "Child"
