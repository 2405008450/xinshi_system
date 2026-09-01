"""
工作流 RESTful API 路由
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from leave_service import assignment_disabled_reason, get_active_leave_map
from workflow_crud import (
    ALL_STAGES,
    get_workflow_by_project,
    get_workflow_by_sub_order,
    get_effective_stages,
    get_management_projects,
    get_my_tasks,
    get_project_manager_candidates,
    get_project_role_candidates,
    claim_management_projects,
    claim_management_project_refs,
    get_transferable_tasks,
    get_eligible_transfer_users,
    get_eligible_transfer_users_unified,
    create_handover_request,
    create_handover_request_unified,
    create_project_manager_handover,
    create_project_manager_handover_unified,
    decide_handover_request,
    decide_project_manager_handover,
    list_incoming_handover_requests,
    list_incoming_project_manager_handovers,
    serialize_managed_project,
    serialize_project_manager_handover,
    serialize_handover_request,
    transfer_workflow_tasks,
    transfer_work_items,
    claim_role_pool_tasks,
    claim_role_pool_work_items,
    init_workflow,
    set_difficulty,
    transition_forward,
    rollback,
    update_stage_data,
)
from workflow_delegation_service import return_delegations
from workflow_schemas import (
    WorkflowInitRequest,
    SetDifficultyRequest,
    TransitionRequest,
    RollbackRequest,
    StageDataUpdateRequest,
    WorkflowConfigResponse,
    WorkflowStateResponse,
    WorkflowLogResponse,
    WorkflowStageResponse,
    MyTaskItem,
    ManagedProjectItem,
    ProjectManagerHandoverCreate,
    ProjectManagerClaimRequest,
    ProjectManagerHandoverDecisionRequest,
    ProjectManagerHandoverResponse,
    WorkflowHandoverRequest,
    WorkflowHandoverDecisionRequest,
    WorkflowHandoverRequestResponse,
    WorkflowClaimRequest,
    WorkflowRolePoolClaimRequest,
    WorkflowEligibleUsersRequest,
    WorkflowTransferResult,
    WorkflowTransferUser,
    WorkflowDelegationReturnRequest,
)
from models import AppUser
from project_roles import get_stage_role
from routers.auth import get_current_user, require_module_access

router = APIRouter(prefix="/workflow", tags=["workflow"], dependencies=[Depends(require_module_access("projects:read", "workflow:operate"))])


def _split_work_item_refs(refs, legacy_ids):
    workflow_ids = list(dict.fromkeys(legacy_ids or []))
    responsibility_ids = []
    for ref in refs or []:
        if ref.source_kind == 'translation_workflow':
            workflow_ids.append(ref.source_id)
        else:
            responsibility_ids.append(ref.source_id)
    return list(dict.fromkeys(workflow_ids)), list(dict.fromkeys(responsibility_ids))


def _serialize_transfer_users(db: Session, users: list[AppUser]) -> list[WorkflowTransferUser]:
    leave_map = get_active_leave_map(db, [user.id for user in users])
    return [
        WorkflowTransferUser(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            is_on_leave=user.id in leave_map,
            leave_start=leave_map[user.id].start_date if user.id in leave_map else None,
            leave_end=leave_map[user.id].end_date if user.id in leave_map else None,
            assignment_disabled_reason=assignment_disabled_reason(leave_map.get(user.id)),
        )
        for user in users
    ]


def _build_state_response(instance) -> WorkflowStateResponse:
    """将 WorkflowInstance ORM 对象转换为 API 响应字典"""
    assignee_name = None
    if instance.current_assignee:
        assignee_name = instance.current_assignee.full_name or instance.current_assignee.username

    logs = []
    for log in (instance.logs or []):
        operator_name = None
        if log.operator:
            operator_name = log.operator.full_name or log.operator.username
        next_assignee_name = None
        if log.next_assignee:
            next_assignee_name = log.next_assignee.full_name or log.next_assignee.username

        logs.append(WorkflowLogResponse(
            id=log.id,
            operator_id=log.operator_id,
            operator_name=operator_name,
            from_stage=log.from_stage,
            to_stage=log.to_stage,
            direction=log.direction,
            description=log.description,
            note=log.note,
            next_assignee_id=log.next_assignee_id,
            next_assignee_name=next_assignee_name,
            created_at=log.created_at,
        ))

    sub_order_no = None
    if instance.sub_order_id and instance.sub_order:
        sub_order_no = instance.sub_order.sub_order_no

    effective_stages = [
        WorkflowStageResponse(**stage)
        for stage in get_effective_stages(instance.difficulty, instance.file_editable)
    ]
    stage_role = get_stage_role(instance.current_stage_key)
    project = instance.translation_project
    if not project and instance.sub_order:
        project = instance.sub_order.parent_project

    return WorkflowStateResponse(
        id=instance.id,
        translation_project_id=instance.translation_project_id,
        sub_order_id=instance.sub_order_id,
        sub_order_no=sub_order_no,
        difficulty=instance.difficulty,
        file_editable=instance.file_editable,
        current_stage_key=instance.current_stage_key,
        current_stage_role_code=stage_role['role_code'],
        current_stage_role_name=stage_role['role_name'],
        current_assignee_id=instance.current_assignee_id,
        current_assignee_name=assignee_name,
        group_assign_role=instance.group_assign_role,
        project_status=instance.project_status,
        stage_notes=instance.stage_notes,
        stage_data=instance.stage_data,
        effective_stages=effective_stages,
        role_assignments=project.role_assignments if project else [],
        logs=logs,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


# ---------- 获取工作流状态 ----------

@router.get("/my-tasks", response_model=list[MyTaskItem])
def get_my_tasks_endpoint(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Return tasks assigned to the current authenticated user."""
    tasks = get_my_tasks(db, current_user.id)
    return tasks


@router.get("/management-projects", response_model=list[ManagedProjectItem])
def get_management_projects_endpoint(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """管理层项目归属列表，与执行阶段任务列表分离。"""
    return get_management_projects(db, current_user)


@router.get("/project-manager-candidates", response_model=list[WorkflowTransferUser])
def get_project_manager_candidates_endpoint(
    include_current: bool = False,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return _serialize_transfer_users(
        db,
        get_project_manager_candidates(db, current_user.id, include_current=include_current),
    )


@router.get("/role-candidates/{role_code}", response_model=list[WorkflowTransferUser])
def get_project_role_candidates_endpoint(
    role_code: str,
    db: Session = Depends(get_db),
):
    try:
        return _serialize_transfer_users(db, get_project_role_candidates(db, role_code))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/project-manager-claim", response_model=list[ManagedProjectItem])
def claim_management_projects_endpoint(
    payload: ProjectManagerClaimRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        if payload.project_refs:
            return claim_management_project_refs(db, current_user, payload.project_refs)
        projects = claim_management_projects(db, current_user=current_user, translation_project_ids=payload.translation_project_ids)
        return [serialize_managed_project(project) for project in projects]
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/project-manager-handover",
    response_model=ProjectManagerHandoverResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project_manager_handover_endpoint(
    payload: ProjectManagerHandoverCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        if payload.project_refs:
            request = create_project_manager_handover_unified(
                db, current_user, payload.project_refs, payload.target_manager_id, payload.reason, payload.note
            )
        else:
            request = create_project_manager_handover(
                db, requester=current_user, translation_project_ids=payload.translation_project_ids,
                target_manager_id=payload.target_manager_id, reason=payload.reason, note=payload.note,
            )
        return serialize_project_manager_handover(request)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/project-manager-handover/incoming",
    response_model=list[ProjectManagerHandoverResponse],
)
def list_incoming_project_manager_handovers_endpoint(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    requests = list_incoming_project_manager_handovers(db, current_user.id)
    return [serialize_project_manager_handover(item) for item in requests]


def _decide_project_manager_handover_endpoint(
    request_id: UUID,
    payload: ProjectManagerHandoverDecisionRequest,
    decision: str,
    db: Session,
    current_user: AppUser,
):
    try:
        request = decide_project_manager_handover(
            db,
            request_id,
            current_user,
            decision,
            payload.note,
        )
        return serialize_project_manager_handover(request)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post(
    "/project-manager-handover/{request_id}/accept",
    response_model=ProjectManagerHandoverResponse,
)
def accept_project_manager_handover_endpoint(
    request_id: UUID,
    payload: ProjectManagerHandoverDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return _decide_project_manager_handover_endpoint(
        request_id,
        payload,
        'accept',
        db,
        current_user,
    )


@router.post(
    "/project-manager-handover/{request_id}/reject",
    response_model=ProjectManagerHandoverResponse,
)
def reject_project_manager_handover_endpoint(
    request_id: UUID,
    payload: ProjectManagerHandoverDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return _decide_project_manager_handover_endpoint(
        request_id,
        payload,
        'reject',
        db,
        current_user,
    )


@router.get("/transferable-tasks", response_model=list[MyTaskItem])
def get_transferable_tasks_endpoint(
    owner_user_id: Optional[UUID] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    return get_transferable_tasks(db, current_user.id, owner_user_id=owner_user_id, keyword=keyword)


@router.post("/eligible-users", response_model=list[WorkflowTransferUser])
def get_eligible_transfer_users_endpoint(
    payload: WorkflowEligibleUsersRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        workflow_ids, responsibility_ids = _split_work_item_refs(payload.work_item_refs, payload.workflow_instance_ids)
        users = get_eligible_transfer_users_unified(db, workflow_ids, responsibility_ids)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_transfer_users(db, users)


@router.post("/handover", response_model=WorkflowHandoverRequestResponse, status_code=status.HTTP_201_CREATED)
def handover_tasks_endpoint(
    payload: WorkflowHandoverRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        workflow_ids, responsibility_ids = _split_work_item_refs(payload.work_item_refs, payload.workflow_instance_ids)
        request = create_handover_request_unified(
            db,
            requester=current_user,
            workflow_instance_ids=workflow_ids,
            project_responsibility_ids=responsibility_ids,
            target_user_id=payload.target_user_id,
            handover_type=payload.handover_type,
            transfer_mode=payload.transfer_mode,
            delegation_end_at=payload.delegation_end_at,
            reason_detail=payload.reason_detail,
            content=payload.content,
            content_json=payload.content_json,
            attachment_ids=payload.attachment_ids,
        )
        db.expire_all()
        created = next(
            (
                item for item in list_incoming_handover_requests(db, payload.target_user_id)
                if item.id == request.id
            ),
            request,
        )
        return serialize_handover_request(created)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/handover-requests/incoming", response_model=list[WorkflowHandoverRequestResponse])
def list_incoming_handover_requests_endpoint(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    requests = list_incoming_handover_requests(db, current_user.id)
    return [serialize_handover_request(item) for item in requests]


@router.post("/handover-requests/{request_id}/accept", response_model=WorkflowHandoverRequestResponse)
def accept_handover_request_endpoint(
    request_id: UUID,
    payload: WorkflowHandoverDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        decided = decide_handover_request(db, request_id, current_user, 'accept', payload.note)
        db.expire_all()
        return serialize_handover_request(decided)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/handover-requests/{request_id}/reject", response_model=WorkflowHandoverRequestResponse)
def reject_handover_request_endpoint(
    request_id: UUID,
    payload: WorkflowHandoverDecisionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        decided = decide_handover_request(db, request_id, current_user, 'reject', payload.note)
        db.expire_all()
        return serialize_handover_request(decided)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/delegations/return", response_model=WorkflowTransferResult)
def return_delegated_tasks_endpoint(
    payload: WorkflowDelegationReturnRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        return return_delegations(db, payload.delegation_ids, current_user, payload.note)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/claim", response_model=WorkflowTransferResult)
def claim_tasks_endpoint(
    payload: WorkflowClaimRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        workflow_ids, responsibility_ids = _split_work_item_refs(payload.work_item_refs, payload.workflow_instance_ids)
        return transfer_work_items(
            db,
            operator=current_user,
            workflow_instance_ids=workflow_ids,
            project_responsibility_ids=responsibility_ids,
            action='claim',
            content=payload.content,
            content_json=payload.content_json,
            attachment_ids=payload.attachment_ids,
            expected_assignee_ids=payload.expected_assignee_ids,
        )
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/role-pool-claim", response_model=WorkflowTransferResult)
def claim_role_pool_tasks_endpoint(
    payload: WorkflowRolePoolClaimRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    try:
        workflow_ids, responsibility_ids = _split_work_item_refs(payload.work_item_refs, payload.workflow_instance_ids)
        return claim_role_pool_work_items(db, current_user, workflow_ids, responsibility_ids)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/config", response_model=WorkflowConfigResponse)
def get_workflow_config():
    """返回基础工作流阶段定义，供前端展示或兜底使用"""
    return WorkflowConfigResponse(
        all_stages=[WorkflowStageResponse(**stage) for stage in ALL_STAGES]
    )


@router.get("/{project_id}", response_model=WorkflowStateResponse)
def get_workflow_state(project_id: UUID, db: Session = Depends(get_db)):
    """获取项目的工作流状态（含操作日志）"""
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该项目尚未初始化工作流"
        )
    return _build_state_response(instance)


# ---------- 初始化 ----------

@router.post("/{project_id}/init", response_model=WorkflowStateResponse, status_code=status.HTTP_201_CREATED)
def init_workflow_endpoint(project_id: UUID, db: Session = Depends(get_db)):
    """初始化项目的工作流"""
    try:
        instance = init_workflow(db, project_id)
        return _build_state_response(instance)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ---------- 设定难度 ----------

@router.post("/{project_id}/set-difficulty", response_model=WorkflowStateResponse)
def set_difficulty_endpoint(
    project_id: UUID,
    request: SetDifficultyRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """客户专员设定难度并推进到下一阶段"""
    try:
        instance = set_difficulty(
            db,
            project_id=project_id,
            difficulty=request.difficulty,
            file_editable=request.file_editable,
            next_assignee_id=request.next_assignee_id,
            group_assign_role=request.group_assign_role,
            operator_id=current_user.id,
            note=request.note,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ---------- 阶段推进 ----------

@router.post("/{project_id}/transition", response_model=WorkflowStateResponse)
def transition_endpoint(
    project_id: UUID,
    request: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """完成当前阶段，推进到下一阶段"""
    try:
        instance = transition_forward(
            db,
            project_id=project_id,
            next_assignee_id=request.next_assignee_id,
            group_assign_role=request.group_assign_role,
            operator_id=current_user.id,
            note=request.note,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ---------- 打回 ----------

@router.post("/{project_id}/rollback", response_model=WorkflowStateResponse)
def rollback_endpoint(
    project_id: UUID,
    request: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """打回操作"""
    try:
        instance = rollback(
            db,
            project_id=project_id,
            steps=request.steps,
            to_start=request.to_start,
            note=request.note,
            operator_id=current_user.id,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ---------- 更新阶段进度数据 ----------

@router.put("/{project_id}/stage-data", response_model=WorkflowStateResponse)
def update_stage_data_endpoint(
    project_id: UUID,
    request: StageDataUpdateRequest,
    db: Session = Depends(get_db),
):
    """更新（暂存）当前阶段的进度表单数据"""
    try:
        instance = update_stage_data(
            db,
            project_id=project_id,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================
# 子订单工作流路由（与母订单路由逻辑一致，通过 sub_order_id 路由）
# ============================================================

@router.get("/suborder/{sub_order_id}", response_model=WorkflowStateResponse)
def get_sub_order_workflow_state(sub_order_id: UUID, db: Session = Depends(get_db)):
    """获取子订单的工作流状态"""
    instance = get_workflow_by_sub_order(db, sub_order_id)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该子订单尚未初始化工作流")
    return _build_state_response(instance)


@router.post("/suborder/{sub_order_id}/init", response_model=WorkflowStateResponse, status_code=status.HTTP_201_CREATED)
def init_sub_order_workflow_endpoint(sub_order_id: UUID, db: Session = Depends(get_db)):
    """初始化子订单工作流"""
    try:
        instance = init_workflow(db, sub_order_id=sub_order_id)
        return _build_state_response(instance)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/suborder/{sub_order_id}/set-difficulty", response_model=WorkflowStateResponse)
def set_sub_order_difficulty_endpoint(
    sub_order_id: UUID,
    request: SetDifficultyRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """子订单接稿：设定难度并推进"""
    try:
        instance = set_difficulty(
            db,
            sub_order_id=sub_order_id,
            difficulty=request.difficulty,
            file_editable=request.file_editable,
            next_assignee_id=request.next_assignee_id,
            group_assign_role=request.group_assign_role,
            operator_id=current_user.id,
            note=request.note,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/suborder/{sub_order_id}/transition", response_model=WorkflowStateResponse)
def transition_sub_order_endpoint(
    sub_order_id: UUID,
    request: TransitionRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """子订单完成当前阶段，推进到下一阶段"""
    try:
        instance = transition_forward(
            db,
            sub_order_id=sub_order_id,
            next_assignee_id=request.next_assignee_id,
            group_assign_role=request.group_assign_role,
            operator_id=current_user.id,
            note=request.note,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/suborder/{sub_order_id}/rollback", response_model=WorkflowStateResponse)
def rollback_sub_order_endpoint(
    sub_order_id: UUID,
    request: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """子订单打回操作"""
    try:
        instance = rollback(
            db,
            sub_order_id=sub_order_id,
            steps=request.steps,
            to_start=request.to_start,
            note=request.note,
            operator_id=current_user.id,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/suborder/{sub_order_id}/stage-data", response_model=WorkflowStateResponse)
def update_sub_order_stage_data_endpoint(
    sub_order_id: UUID,
    request: StageDataUpdateRequest,
    db: Session = Depends(get_db),
):
    """子订单：更新（暂存）当前阶段的进度表单数据"""
    try:
        instance = update_stage_data(
            db,
            sub_order_id=sub_order_id,
            stage_data=request.stage_data,
        )
        return _build_state_response(instance)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
