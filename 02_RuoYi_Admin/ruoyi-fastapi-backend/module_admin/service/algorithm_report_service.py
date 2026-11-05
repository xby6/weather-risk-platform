"""Isolated LLM generation and restart-safe background report processing."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from config.database import AsyncSessionLocal
from module_admin.service.algorithm_report_prompt import (
    SYSTEM_PROMPT, build_evidence, build_prompt, render_markdown, validate_analysis,
)
from module_admin.service.algorithm_report_store import (
    claim_report, dumps, enqueue_auto_report, ensure_report_tables, get_config, get_enabled_model, model_info,
)
from utils.log_util import logger


async def call_report_llm(model_config: dict[str, Any], prompt: str) -> str:
    from agno.agent import Agent
    from utils.ai_util import AiUtil
    from utils.crypto_util import CryptoUtil

    api_key = CryptoUtil.decrypt(model_config['api_key']) if model_config.get('api_key') else None
    model = AiUtil.get_model_from_factory(
        provider=model_config['provider'], model_code=model_config['model_code'], model_name=model_config['model_name'],
        api_key=api_key, base_url=model_config.get('base_url'), temperature=model_config.get('temperature'),
        max_tokens=model_config.get('max_tokens') or 4096,
    )
    agent = Agent(model=model, instructions=SYSTEM_PROMPT, markdown=False, add_history_to_context=False, telemetry=False)
    response = await asyncio.wait_for(agent.arun(prompt, stream=False), timeout=120)
    content = response.content
    if isinstance(content, dict):
        content = dumps(content)
    if not isinstance(content, str) or not content.strip():
        raise ValueError('LLM返回空报告')
    return content


async def generate_report(record: dict[str, Any], session_factory=AsyncSessionLocal) -> None:
    params = {'id': record['id'], 'token': record['lease_token']}
    try:
        facts = await asyncio.to_thread(build_evidence, json.loads(record['snapshot_json']), record.get('snapshot_path') or '')
        prompt = build_prompt(facts, record.get('instructions') or '')
        async with session_factory() as db:
            model = await get_enabled_model(db, record['model_id'])
            original = json.loads(record['model_info'])
            if any(original.get(key) != model.get(key) for key in ('provider', 'model_code')):
                raise ValueError('LLM配置已变更，请重新生成新版本报告')
            saved = await db.execute(text('''UPDATE algorithm_report SET facts_json = :facts, prompt = :prompt,
                model_info = :model_info, update_time = :now WHERE id = :id AND lease_token = :token AND report_status = 'running' '''),
                {**params, 'facts': dumps(facts), 'prompt': prompt, 'model_info': dumps(model_info(model)), 'now': datetime.now()})
            await db.commit()
            if not saved.rowcount:
                return
        try:
            raw = await call_report_llm(model, prompt)
        except TimeoutError:
            raise
        except Exception as exc:
            raise RuntimeError(f'LLM调用失败（{type(exc).__name__}）') from None
        analysis = validate_analysis(raw, facts)
        content = render_markdown(record['title'], analysis, facts)
        async with session_factory() as db:
            await db.execute(text('''UPDATE algorithm_report SET report_status = 'success', analysis_json = :analysis,
                content = :content, error_message = NULL, lease_token = NULL, lease_until = NULL, update_time = :now
                WHERE id = :id AND lease_token = :token AND report_status = 'running' '''),
                {**params, 'analysis': dumps(analysis), 'content': content, 'now': datetime.now()})
            await db.commit()
    except asyncio.CancelledError:
        # Keep the lease for automatic recovery after restart; never mark the algorithm task failed.
        raise
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else (
            'LLM请求超时' if isinstance(exc, TimeoutError) else f'报告生成失败（{type(exc).__name__}），请检查模型配置或结果文件'
        )
        attempts = int(record['attempts'])
        status = 'failed' if attempts >= 3 else 'queued'
        async with session_factory() as db:
            await db.execute(text('''UPDATE algorithm_report SET report_status = :status, error_message = :error,
                lease_token = NULL, lease_until = NULL, next_attempt_at = :next, update_time = :now
                WHERE id = :id AND lease_token = :token AND report_status = 'running' '''),
                {**params, 'status': status, 'error': message[:1000], 'now': datetime.now(),
                 'next': datetime.now() + timedelta(seconds=15 * 2 ** (attempts - 1))})
            await db.commit()
        logger.warning(f'算法报告 {record["id"]} 生成失败：{type(exc).__name__}，尝试次数 {attempts}')


async def report_queue_loop(session_factory=AsyncSessionLocal) -> None:
    while True:
        try:
            async with session_factory() as db:
                await ensure_report_tables(db)
                record = await claim_report(db)
            if record:
                await asyncio.wait_for(generate_report(record, session_factory), timeout=240)
            else:
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f'算法报告后台处理暂不可用：{type(exc).__name__}')
            await asyncio.sleep(30)


async def sync_report_sources_once(session_factory=AsyncSessionLocal) -> None:
    from module_admin.controller.algorithm_link_controller import get_algorithm_task_status
    from module_admin.service.algorithm_task_store import get_task

    async with session_factory() as db:
        config = await get_config(db)
        if not config['autoEnabled'] or not config['modelId']:
            return
        result = await db.execute(text('''SELECT task_code, task_status FROM algorithm_task
            WHERE task_status IN ('submitted', 'queued', 'running', 'success') ORDER BY update_time DESC'''))
        rows = [dict(row._mapping) for row in result.fetchall()]
    # Separate sessions keep failures on one remote platform from rolling back other tasks.
    for row in rows:
        async with session_factory() as db:
            task = await get_task(db, row['task_code'])
            if not task or not (task.get('rawInputParams') or {}).get('reportRunId'):
                continue
            try:
                if task['status'] in {'submitted', 'queued', 'running'} or task.get('result') in (None, {}, []):
                    await asyncio.wait_for(get_algorithm_task_status(row['task_code'], db), timeout=45)
                else:
                    await enqueue_auto_report(db, task)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await db.rollback()
                logger.warning(f'自动报告数据同步失败：{type(exc).__name__}')


async def report_source_loop(session_factory=AsyncSessionLocal) -> None:
    while True:
        try:
            await sync_report_sources_once(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(f'自动报告状态同步暂不可用：{type(exc).__name__}')
        await asyncio.sleep(10)
