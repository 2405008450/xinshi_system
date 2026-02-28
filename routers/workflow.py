"""
工作流 RESTful API 路由
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from database import get_db
from workflow_crud import (
    get_workflow_by_project,
    get_my_tasks,
    init_workflow,
    set_difficulty,
    transition_forward,
    rollback,
    update_stage_data,
)
from workflow_schemas import (
    WorkflowInitRequest,
    SetDifficultyRequest,
    TransitionRequest,
    RollbackRequest,
    StageDataUpdateRequest,
    WorkflowStateResponse,
    WorkflowLogResponse,
    MyTaskItem,
)
from models import AppUser

router = APIRouter(prefix="/workflow", tags=["workflow"])


def _build_state_response(instance) -> dict:
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

    return WorkflowStateResponse(
        id=instance.id,
        translation_project_id=instance.translation_project_id,
        difficulty=instance.difficulty,
        file_editable=instance.file_editable,
        current_stage_key=instance.current_stage_key,
        current_assignee_id=instance.current_assignee_id,
        current_assignee_name=assignee_name,
        project_status=instance.project_status,
        stage_notes=instance.stage_notes,
        stage_data=instance.stage_data,
        logs=logs,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


# ---------- 获取工作流状态 ----------

@router.get("/my-tasks", response_model=list[MyTaskItem])
def get_my_tasks_endpoint(
    user_id: str = Query(..., description="当前用户ID"),
    db: Session = Depends(get_db),
):
    """获取当前用户的待办任务列表"""
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")
    tasks = get_my_tasks(db, user_uuid)
    return tasks


@router.get("/{project_id}", response_model=WorkflowStateResponse)
def get_workflow_state(project_id: UUID, db: Session = Depends(get_db)):
    """获取项目的工作流状态（含操作日志）"""
    instance = get_workflow_by_project(db, project_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found for this project"
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
):
    """客户专员设定难度并推进到下一阶段"""
    try:
        instance = set_difficulty(
            db,
            project_id=project_id,
            difficulty=request.difficulty,
            file_editable=request.file_editable,
            next_assignee_id=request.next_assignee_id,
            operator_id=request.operator_id,
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
):
    """完成当前阶段，推进到下一阶段"""
    try:
        instance = transition_forward(
            db,
            project_id=project_id,
            next_assignee_id=request.next_assignee_id,
            operator_id=request.operator_id,
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
):
    """打回操作"""
    try:
        instance = rollback(
            db,
            project_id=project_id,
            steps=request.steps,
            to_start=request.to_start,
            note=request.note,
            operator_id=request.operator_id,
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
