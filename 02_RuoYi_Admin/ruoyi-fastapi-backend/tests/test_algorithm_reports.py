from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from module_admin.service import algorithm_report_prompt as prompt
from module_admin.service import algorithm_report_service as service
from module_admin.service import algorithm_report_store as reports
from module_admin.service import algorithm_task_store as tasks
from test_algorithm_task_history import SqliteSession


class ReportSession(SqliteSession):
    def __init__(self):
        super().__init__()
        self.connection.executescript('''
            CREATE TABLE ai_models (model_id INTEGER PRIMARY KEY, model_code TEXT, model_name TEXT,
                provider TEXT, api_key TEXT, base_url TEXT, temperature REAL, max_tokens INTEGER, status TEXT);
            INSERT INTO ai_models VALUES (1, 'test-model', '测试LLM', 'DeepSeek', 'encrypted-secret',
                'http://localhost/mock', 0.2, 4096, '0');
            CREATE TABLE algorithm_report_config (id INTEGER PRIMARY KEY, model_id INTEGER,
                auto_enabled INTEGER, auto_since TEXT, instructions TEXT, update_time TEXT DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO algorithm_report_config (id, model_id, auto_enabled, auto_since, instructions)
                VALUES (1, 1, 1, '2000-01-01', '关注高风险对象');
            CREATE TABLE algorithm_report (
                id TEXT PRIMARY KEY, task_code TEXT, source_key TEXT, version INTEGER, title TEXT,
                report_status TEXT DEFAULT 'queued', model_id INTEGER, model_info TEXT, snapshot_json TEXT,
                snapshot_path TEXT, instructions TEXT, facts_json TEXT, prompt TEXT, analysis_json TEXT, content TEXT,
                error_message TEXT, attempts INTEGER DEFAULT 0, lease_token TEXT, lease_until TEXT,
                next_attempt_at TEXT DEFAULT CURRENT_TIMESTAMP, create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(source_key, version));
        ''')

    async def execute(self, statement, params=None):
        sql = str(statement)
        if 'ON DUPLICATE KEY UPDATE' in sql:
            from sqlalchemy import text
            sql = sql.split('ON DUPLICATE KEY UPDATE')[0] + '''ON CONFLICT(id) DO UPDATE SET
                model_id = excluded.model_id, auto_enabled = excluded.auto_enabled,
                auto_since = excluded.auto_since, instructions = excluded.instructions, update_time = CURRENT_TIMESTAMP'''
            statement = text(sql)
        return await super().execute(statement, params)


class AlgorithmReportPromptTest(unittest.TestCase):
    def test_full_workbook_statistics_include_rows_beyond_ui_preview_limit(self):
        import pandas as pd
        frame = pd.DataFrame({'杆塔编号': [f'T{i}' for i in range(5001)], '故障概率': [0.1] * 5000 + [0.99],
                              '概率等级': ['低'] * 5000 + ['高'], '预测时间': ['2026-10-07 08:00:00'] * 5001})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.xlsx'
            frame.to_excel(path, sheet_name='未来故障预测', index=False)
            facts = prompt.build_evidence({'task': {}, 'algorithm': {}, 'result': {'result_type': 'file'}}, str(path))
        stats = next(source['data'] for source in facts['evidence'] if source['title'] == '工作表：未来故障预测')
        self.assertEqual(stats['recordCount'], 5001)
        self.assertEqual(stats['numericStatistics']['故障概率']['max'], 0.99)
        self.assertEqual(stats['riskDistribution'], {'低': 5000, '高': 1})
        self.assertEqual(stats['representativeRecords'][0]['杆塔编号'], 'T5000')

    def test_json_statistics_secrets_and_nonfinite_numbers(self):
        result = {'summary': {'max_wind_speed': 20}, 'api_key': 'do-not-send', 'output_file': 'private-path',
                  'result': [{'wind_speed': 10, 'risk_level': '黄色', 'token': 'do-not-send'},
                             {'wind_speed': 20, 'risk_level': '红色', 'probability': float('nan')}]}
        facts = prompt.build_evidence({'task': {'params': {'password': 'do-not-send'}}, 'result': result})
        message = prompt.build_prompt(facts)
        self.assertNotIn('do-not-send', message)
        self.assertNotIn('private-path', message)
        self.assertNotIn('NaN', message)
        stats = facts['evidence'][-1]['data']
        self.assertEqual(stats['numericStatistics']['wind_speed']['mean'], 15)
        self.assertEqual(stats['riskDistribution']['红色'], 1)

    def test_report_output_requires_valid_evidence_and_all_sections(self):
        facts = {'evidence': [{'id': 'S1'}]}
        response = {'summary': '结果摘要', 'analysis': ['分析[S1]'], 'risks': ['风险[S1]'],
                    'recommendations': ['核实风险[S1]'], 'limitations': ['无真实故障反馈']}
        self.assertEqual(prompt.validate_analysis(json.dumps(response), facts), response)
        for invalid in ('不存在的证据[S9]', '缺少依据'):
            response['risks'] = [invalid]
            with self.assertRaises(ValueError):
                prompt.validate_analysis(json.dumps(response), facts)
        with self.assertRaises(ValueError):
            prompt.validate_analysis('不是JSON', facts)

    def test_list_result_and_file_evidence_have_unique_references(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.csv'
            path.write_text('wind_speed\n10\n20\n', encoding='utf-8')
            facts = prompt.build_evidence({'task': {}, 'result': [{'wind_speed': 10}]}, str(path))
        ids = [source['id'] for source in facts['evidence']]
        self.assertEqual(ids, ['S1', 'S2', 'S3', 'S4'])

    def test_unsupported_file_without_summary_does_not_invent_analysis(self):
        with self.assertRaisesRegex(ValueError, '尚未适配'):
            prompt.build_evidence({'task': {}, 'result': {'result_type': 'file'}}, 'result.zip')


class AlgorithmReportFlowTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = ReportSession()
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.patch_dir = patch.object(reports, 'REPORT_DIR', root / 'reports')
        self.patch_results = patch.object(reports, 'RESULT_DIR', root / 'results')
        self.patch_algorithm = patch('module_admin.service.algorithm_model_store.get_model_by_algorithm_id',
                                     AsyncMock(return_value={'algorithmName': '大风风险', 'outputSchema': 'wind_speed: m/s'}))
        self.patch_dir.start()
        self.patch_results.start()
        self.patch_algorithm.start()
        await tasks.create_task(self.db, {'taskCode': 'TASK_R', 'taskName': '风险测试', 'algorithmId': 'wind_risk_forecast'})
        await tasks.claim_task_run(self.db, 'TASK_R')
        self.result = {'summary': {'max_wind_speed': 20}, 'result': [{'wind_speed': 20, 'risk_level': '红色'}]}
        await tasks.update_task(self.db, 'TASK_R', status='success', result=self.result)

    async def asyncTearDown(self):
        self.patch_algorithm.stop()
        self.patch_results.stop()
        self.patch_dir.stop()
        self.db.connection.close()
        self.temporary.cleanup()

    @asynccontextmanager
    async def session_factory(self):
        try:
            yield self.db
        except BaseException:
            await self.db.rollback()
            raise

    def llm_response(self):
        return json.dumps({'summary': '重点关注预测风险', 'analysis': ['最大风速为20[S3]'], 'risks': ['算法输出红色风险[S4]'],
                           'recommendations': ['优先核实重点线路[S4]'], 'limitations': ['未提供实际故障反馈']}, ensure_ascii=False)

    async def test_duplicate_queue_claim_generation_and_downloadable_content(self):
        first = await reports.enqueue_report(self.db, 'TASK_R')
        same = await reports.enqueue_report(self.db, 'TASK_R')
        self.assertEqual(first['id'], same['id'])
        self.assertNotIn('encrypted-secret', json.dumps(first))
        claimed = await reports.claim_report(self.db)
        self.assertIsNone(await reports.claim_report(self.db))
        with patch.object(service, 'call_report_llm', AsyncMock(return_value=self.llm_response())) as llm:
            await service.generate_report(claimed, self.session_factory)
        report = await reports.get_report(self.db, first['id'])
        self.assertEqual(report['status'], 'success')
        self.assertIn('## 处理建议', report['content'])
        self.assertIn('20', report['content'])
        self.assertNotIn('encrypted-secret', llm.call_args.args[1])
        self.assertFalse(await reports.retry_report(self.db, first['id']))

    async def test_rerun_and_regeneration_preserve_original_snapshot(self):
        first = await reports.enqueue_report(self.db, 'TASK_R')
        self.db.connection.execute("UPDATE algorithm_report SET report_status='success' WHERE id=?", (first['id'],))
        self.db.connection.commit()
        new_version = await reports.enqueue_report(self.db, 'TASK_R', force=True)
        self.assertEqual(new_version['version'], 2)
        await tasks.claim_task_run(self.db, 'TASK_R')
        await tasks.update_task(self.db, 'TASK_R', status='success', result={'summary': {'max_wind_speed': 3}})
        rerun = await reports.enqueue_report(self.db, 'TASK_R')
        self.assertNotEqual(first['id'], rerun['id'])
        snapshot = self.db.connection.execute('SELECT snapshot_json FROM algorithm_report WHERE id=?', (first['id'],)).fetchone()[0]
        self.assertEqual(json.loads(snapshot)['result']['summary']['max_wind_speed'], 20)
        task = await tasks.get_task(self.db, 'TASK_R')
        self.assertNotIn('reportRunId', task['params'])

    async def test_file_snapshot_survives_overwriting_original(self):
        reports.RESULT_DIR.mkdir()
        original = reports.RESULT_DIR / 'result.csv'
        original.write_text('风速\n20\n', encoding='utf-8')
        await tasks.update_task(self.db, 'TASK_R', result={'result_type': 'file', 'summary': {'count': 1}}, resultPath=str(original.resolve()))
        report = await reports.enqueue_report(self.db, 'TASK_R')
        original.write_text('风速\n1\n', encoding='utf-8')
        row = self.db.connection.execute('SELECT snapshot_path FROM algorithm_report WHERE id=?', (report['id'],)).fetchone()
        self.assertIn('20', Path(row[0]).read_text(encoding='utf-8'))
        self.assertEqual(reports.snapshot_result_file(str(Path(self.temporary.name) / 'outside.csv'), 'outside'), '')

    async def test_llm_failure_retries_then_failed_without_changing_task(self):
        queued = await reports.enqueue_report(self.db, 'TASK_R')
        with patch.object(service, 'call_report_llm', AsyncMock(side_effect=RuntimeError('secret-provider-error'))):
            for attempt in range(3):
                self.db.connection.execute('UPDATE algorithm_report SET next_attempt_at=? WHERE id=?', ('2000-01-01', queued['id']))
                self.db.connection.commit()
                claimed = await reports.claim_report(self.db)
                self.assertIsNotNone(claimed)
                await service.generate_report(claimed, self.session_factory)
        report = await reports.get_report(self.db, queued['id'])
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('secret-provider-error', report['error'])
        self.assertEqual((await tasks.get_task(self.db, 'TASK_R'))['status'], 'success')
        self.assertTrue(await reports.retry_report(self.db, queued['id']))
        self.assertEqual((await reports.claim_report(self.db))['attempts'], 1)

    async def test_expired_lease_recovery_rejects_stale_writer(self):
        queued = await reports.enqueue_report(self.db, 'TASK_R')
        old = await reports.claim_report(self.db)
        self.db.connection.execute('UPDATE algorithm_report SET lease_until=? WHERE id=?', ('2000-01-01', queued['id']))
        self.db.connection.commit()
        current = await reports.claim_report(self.db)
        self.assertNotEqual(old['lease_token'], current['lease_token'])
        with patch.object(service, 'call_report_llm', AsyncMock(return_value=self.llm_response())) as llm:
            await service.generate_report(old, self.session_factory)
            llm.assert_not_called()
            await service.generate_report(current, self.session_factory)
        self.assertEqual((await reports.get_report(self.db, queued['id']))['status'], 'success')

    async def test_auto_reports_skip_legacy_and_runs_before_enabled_time(self):
        task = await tasks.get_task(self.db, 'TASK_R')
        legacy = {**task, 'rawInputParams': {}}
        await reports.enqueue_auto_report(self.db, legacy)
        self.assertEqual(await reports.list_reports(self.db, 'TASK_R'), [])
        await reports.save_config(self.db, 1, False, '')
        await reports.enqueue_auto_report(self.db, task)
        self.assertEqual(await reports.list_reports(self.db, 'TASK_R'), [])
        await reports.save_config(self.db, 1, True, '')
        await reports.enqueue_auto_report(self.db, task)
        self.assertEqual(await reports.list_reports(self.db, 'TASK_R'), [])
        await tasks.claim_task_run(self.db, 'TASK_R')
        await tasks.update_task(self.db, 'TASK_R', status='success', result=self.result)
        await reports.enqueue_auto_report(self.db, await tasks.get_task(self.db, 'TASK_R'))
        self.assertEqual(len(await reports.list_reports(self.db, 'TASK_R')), 1)

    async def test_backend_sync_can_queue_report_without_frontend(self):
        await tasks.claim_task_run(self.db, 'TASK_R')
        async def finished(code, db):
            await tasks.update_task(db, code, status='success', result=self.result)
        with patch('module_admin.controller.algorithm_link_controller.get_algorithm_task_status', side_effect=finished):
            await service.sync_report_sources_once(self.session_factory)
            await service.sync_report_sources_once(self.session_factory)
        self.assertEqual(len(await reports.list_reports(self.db, 'TASK_R')), 1)

    async def test_backend_sync_fetches_result_when_submission_already_succeeded(self):
        await tasks.claim_task_run(self.db, 'TASK_R')
        await tasks.update_task(self.db, 'TASK_R', status='success', result=None)
        async def fetched(code, db):
            await tasks.update_task(db, code, status='success', result=self.result)
        with patch('module_admin.controller.algorithm_link_controller.get_algorithm_task_status', side_effect=fetched) as fetch:
            await service.sync_report_sources_once(self.session_factory)
            await service.sync_report_sources_once(self.session_factory)
            fetch.assert_called_once()
        self.assertEqual(len(await reports.list_reports(self.db, 'TASK_R')), 1)

    async def test_actual_llm_adapter_with_mock_http_transport(self):
        import httpx
        from utils.ai_util import AiUtil
        from utils.crypto_util import CryptoUtil

        requests = []
        def response_handler(request):
            payload = json.loads(request.content)
            requests.append(payload)
            return httpx.Response(200, json={'id': 'mock-completion', 'object': 'chat.completion', 'created': 1,
                'model': 'test-model', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': self.llm_response()},
                    'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 100, 'total_tokens': 200}})

        factory = AiUtil.get_model_from_factory
        async with httpx.AsyncClient(transport=httpx.MockTransport(response_handler)) as client:
            def factory_with_transport(**kwargs):
                return factory(**kwargs, http_client=client)
            model = await reports.get_enabled_model(self.db, 1)
            with patch.object(AiUtil, 'get_model_from_factory', side_effect=factory_with_transport), \
                 patch.object(CryptoUtil, 'decrypt', return_value='mock-api-key') as decrypt:
                output = await service.call_report_llm(model, '仅分析提供的数据证据')
            decrypt.assert_called_once_with('encrypted-secret')
        self.assertEqual(json.loads(output)['summary'], '重点关注预测风险')
        self.assertEqual(requests[0]['model'], 'test-model')
        self.assertFalse(requests[0].get('stream', False))
        self.assertIn('不可编造', requests[0]['messages'][0]['content'])

    async def test_http_report_routes_auth_generation_detail_retry_and_download(self):
        import httpx
        from fastapi import FastAPI
        from common.context import RequestContext
        from config.get_db import get_db
        from exceptions.handle import handle_exception
        from module_admin.controller import algorithm_report_controller as controller
        from types import SimpleNamespace

        app = FastAPI()
        app.include_router(controller.router)
        handle_exception(app)
        app.dependency_overrides[get_db] = lambda: self.db
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
            denied = await client.get('/algorithm/report/config')
            self.assertEqual(denied.json()['code'], 401)
            auth_call = controller.router.dependencies[0].dependency
            async def logged_in():
                user = SimpleNamespace(permissions=[])
                RequestContext.set_current_user(user)
                RequestContext.set_current_exclude_patterns([])
                return user
            app.dependency_overrides[auth_call] = logged_in
            config_denied = await client.put('/algorithm/report/config', json={'modelId': 1})
            self.assertEqual(config_denied.json()['code'], 403)
            created = await client.post('/algorithm/report/task/TASK_R')
            self.assertTrue(created.json()['success'])
            report_id = created.json()['data']['id']
            pending = await client.get(f'/algorithm/report/{report_id}/download')
            self.assertFalse(pending.json()['success'])
            queued = await reports.claim_report(self.db)
            with patch.object(service, 'call_report_llm', AsyncMock(return_value=self.llm_response())):
                await service.generate_report(queued, self.session_factory)
            detail = await client.get(f'/algorithm/report/{report_id}')
            self.assertEqual(detail.json()['data']['status'], 'success')
            self.assertNotIn('encrypted-secret', detail.text)
            downloaded = await client.get(f'/algorithm/report/{report_id}/download')
            self.assertIn('text/markdown', downloaded.headers['content-type'])
            self.assertIn('## 处理建议', downloaded.text)
            self.assertIn('attachment;', downloaded.headers['content-disposition'])
            listed = await client.get('/algorithm/report/task/TASK_R')
            self.assertEqual(len(listed.json()['data']['rows']), 1)
            invalid_retry = await client.post(f'/algorithm/report/{report_id}/retry')
            self.assertFalse(invalid_retry.json()['success'])


if __name__ == '__main__':
    unittest.main()
