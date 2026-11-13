"""供其他项目或 AI 客户端消费的小语种转写报告只读接口。"""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from annotation_transcription_report_service import ReportDataError, get_report_dataset
from routers.auth import require_permission


router = APIRouter(
    prefix="/projects/annotation-transcription-report",
    tags=["annotation_transcription_report"],
    dependencies=[Depends(require_permission("projects:read"))],
    responses={401: {"description": "未登录或登录已过期"},
               403: {"description": "缺少 projects:read 权限"},
               503: {"description": "报告数据包缺失或损坏"}},
)


class DetailPage(BaseModel):
    report_id: str
    revision: str
    language_code: str
    filters: dict[str, Any]
    skip: int
    limit: int
    total: int
    items: list[dict[str, Any]]


def report_dataset():
    try:
        return get_report_dataset()
    except ReportDataError as exc:
        raise HTTPException(503, detail=str(exc)) from exc


@router.get("", summary="读取报告版本、模型目录、统计口径与字段说明")
def read_report_metadata(dataset=Depends(report_dataset)) -> dict[str, Any]:
    return dataset.metadata()


@router.get("/summary", summary="读取原始完整汇总 JSON（含语种、逐模型结果及统计口径）")
def read_report_summary(dataset=Depends(report_dataset)) -> dict[str, Any]:
    return dataset.summary


@router.get("/languages", summary="读取语种目录及各语种汇总指标")
def read_report_languages(dataset=Depends(report_dataset)) -> list[dict[str, Any]]:
    return list(dataset.languages.values())


@router.get("/languages/{language_code}/details", response_model=DetailPage,
            summary="按语种分页读取原文与差异指标；支持模型、来源和成功标记筛选",
            responses={404: {"description": "语种不存在"}})
def read_report_details(
    language_code: str = Path(..., min_length=1, max_length=40, pattern=r"^[a-z0-9_]+$"),
    model: str | None = Query(None, min_length=1, max_length=100, description="使用模型目录中的键，例如 qwen"),
    cohort: Literal["public_dataset", "human_independent", "human_revision", "human_after_revision"] | None = None,
    success: bool | None = Query(None, description="只筛选原始返回成功标记，不代表识别质量"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    include_diff_html: bool = Query(False, description="默认只返回原文；开启后附带报告生成的差异高亮 HTML"),
    dataset=Depends(report_dataset),
):
    if model is not None and model not in dataset.summary["models"]:
        raise HTTPException(422, detail="未知模型，请使用报告模型目录中的键")
    try:
        return dataset.details(language_code, model=model, cohort=cohort, success=success,
                               skip=skip, limit=limit, include_diff_html=include_diff_html)
    except KeyError as exc:
        raise HTTPException(404, detail="报告中不存在该语种") from exc
    except ReportDataError as exc:
        raise HTTPException(503, detail=str(exc)) from exc
