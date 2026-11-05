from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.aspect.data_scope import DataScopeDependency
from common.aspect.db_seesion import DBSessionDependency
from common.aspect.interface_auth import UserInterfaceAuthDependency
from common.aspect.pre_auth import PreAuthDependency
from module_admin.service.algorithm_report_store import (
    enqueue_report, ensure_report_tables, get_config, get_enabled_model, get_report, list_reports, retry_report, save_config,
)
from module_ai.entity.do.ai_model_do import AiModels
from module_ai.service.ai_model_service import AiModelService
from utils.response_util import ResponseUtil

router = APIRouter(prefix='/algorithm/report', tags=['算法结果AI报告'], dependencies=[PreAuthDependency()])
DB = Annotated[AsyncSession, DBSessionDependency()]


class ReportSettings(BaseModel):
    modelId: int = Field(gt=0)
    autoEnabled: bool = False
    instructions: str = Field(default='', max_length=4000)


@router.get('/config')
async def report_config(db: DB):
    return ResponseUtil.success(data=await get_config(db))


@router.get('/models')
async def report_models(db: DB, scope: Annotated[ColumnElement, DataScopeDependency(AiModels)]):
    # Do not return API keys, including encrypted or masked keys, to report consumers.
    result = await db.execute(select(AiModels.model_id, AiModels.model_name, AiModels.model_code, AiModels.provider)
                             .where(AiModels.status == '0', scope).order_by(AiModels.model_sort))
    return ResponseUtil.success(data=[{'modelId': row.model_id, 'modelName': row.model_name,
                                      'modelCode': row.model_code, 'provider': row.provider} for row in result.fetchall()])


@router.put('/config', dependencies=[UserInterfaceAuthDependency('ai:model:edit')])
async def update_report_config(payload: ReportSettings, db: DB, scope: Annotated[ColumnElement, DataScopeDependency(AiModels)]):
    await AiModelService.check_ai_model_data_scope_services(db, payload.modelId, scope)
    try:
        await get_enabled_model(db, payload.modelId)
        return ResponseUtil.success(data=await save_config(db, payload.modelId, payload.autoEnabled, payload.instructions), msg='报告设置已保存')
    except ValueError as exc:
        return ResponseUtil.failure(msg=str(exc))


@router.get('/task/{task_code}')
async def task_reports(task_code: str, db: DB):
    return ResponseUtil.success(data={'rows': await list_reports(db, task_code)})


@router.post('/task/{task_code}')
async def create_task_report(task_code: str, db: DB, regenerate: bool = Query(False)):
    try:
        data = await enqueue_report(db, task_code, force=regenerate)
        return ResponseUtil.success(data=data, msg='报告已加入生成队列')
    except ValueError as exc:
        await db.rollback()
        return ResponseUtil.failure(msg=str(exc))


@router.get('/{report_id}')
async def report_detail(report_id: str, db: DB):
    await ensure_report_tables(db)
    report = await get_report(db, report_id)
    if not report:
        return ResponseUtil.failure(msg='报告不存在')
    return ResponseUtil.success(data=report)


@router.post('/{report_id}/retry')
async def report_retry(report_id: str, db: DB):
    await ensure_report_tables(db)
    if not await retry_report(db, report_id):
        return ResponseUtil.failure(msg='仅能重试生成失败的报告')
    return ResponseUtil.success(msg='报告已重新加入生成队列')


@router.get('/{report_id}/download')
async def report_download(report_id: str, db: DB):
    await ensure_report_tables(db)
    report = await get_report(db, report_id)
    if not report or report['status'] != 'success':
        return ResponseUtil.failure(msg='报告尚未生成完成')
    return Response(content=('\ufeff' + report['content']).encode('utf-8'), media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="report-{report_id}.md"'})
