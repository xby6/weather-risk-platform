from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy.exc import ProgrammingError

from module_admin.service import algorithm_task_history as history
from module_admin.service import algorithm_task_store as store


class SqliteSession:
    """Exercise real storage transactions, adapting only MySQL syntax for SQLite."""

    def __init__(self):
        self.connection = sqlite3.connect(':memory:')
        self.connection.row_factory = sqlite3.Row
        self.statements = []
        self.fail_history = False
        columns = '''task_code task_name server_id server_url algorithm_id algorithm_name task_type
            priority region_name line_code file_id forecast_hours start_time end_time input_params task_status
            progress message result_json result_path error_message remark create_by create_time update_time'''.split()
        self.connection.execute('CREATE TABLE algorithm_task (id INTEGER PRIMARY KEY, ' +
                                ', '.join(f'{column} {"INTEGER" if column in {"progress", "forecast_hours"} else "TEXT"}'
                                          for column in columns) + ', UNIQUE(task_code))')
        self.connection.execute('''CREATE TABLE algorithm_task_history (
            id INTEGER PRIMARY KEY, task_code TEXT, task_status TEXT, progress INTEGER,
            message TEXT, error_message TEXT, event_time TEXT DEFAULT CURRENT_TIMESTAMP)''')
        self.connection.commit()

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if self.fail_history and 'INSERT INTO algorithm_task_history' in sql:
            raise RuntimeError('history write failed')
        cursor = self.connection.execute(sql.replace(' FOR UPDATE', '').replace('NOW()', 'CURRENT_TIMESTAMP'), params or {})
        rows = cursor.fetchall()
        return SimpleNamespace(
            rowcount=cursor.rowcount,
            fetchall=lambda: [SimpleNamespace(_mapping=dict(row)) for row in rows],
            fetchone=lambda: SimpleNamespace(_mapping=dict(rows[0])) if rows else None,
            scalar=lambda: rows[0][0] if rows else None,
        )

    async def commit(self):
        self.connection.commit()

    async def rollback(self):
        self.connection.rollback()


class AlgorithmTaskHistoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = SqliteSession()
        await store.create_task(self.db, {'taskCode': 'TASK_1', 'taskName': '测试任务', 'algorithmId': 'icing'})

    async def asyncTearDown(self):
        self.db.connection.close()

    async def test_create_change_and_identical_poll_are_persisted_once(self):
        await store.update_task(self.db, 'TASK_1', status='running', progress=10, message='运行中')
        await store.update_task(self.db, 'TASK_1', status='running', progress=10, message='运行中')
        await store.update_task(self.db, 'TASK_1', status='running', progress=50, message='运行中')
        await store.update_task(self.db, 'TASK_1', status='failed', progress=100, message='失败', error='第一行\n第二行')
        await store.update_task(self.db, 'TASK_1', result={'summary': 'cached'})
        data = await history.list_task_history(self.db, 'TASK_1', 1, 2)
        self.assertEqual(data['total'], 4)
        self.assertEqual([row['progress'] for row in data['rows']], [100, 50])
        self.assertEqual(data['rows'][0]['error'], '第一行\n第二行')
        datetime.fromisoformat(data['rows'][0]['eventTime'])
        page_two = await history.list_task_history(self.db, 'TASK_1', 2, 2)
        self.assertEqual([row['status'] for row in page_two['rows']], ['running', 'created'])
        self.assertTrue(any('FOR UPDATE' in sql for sql in self.db.statements))

    async def test_history_failure_rolls_back_snapshot_with_transaction(self):
        self.db.fail_history = True
        with self.assertRaisesRegex(RuntimeError, 'history write failed'):
            await store.update_task(self.db, 'TASK_1', status='running')
        await self.db.rollback()
        self.db.fail_history = False
        task = await store.get_task(self.db, 'TASK_1')
        self.assertEqual(task['status'], 'created')
        self.assertEqual((await history.list_task_history(self.db, 'TASK_1'))['total'], 1)

    async def test_claim_blocks_repeat_submission_and_resets_old_result(self):
        await store.update_task(self.db, 'TASK_1', status='success', result={'old': True}, resultPath='old.xlsx')
        self.assertTrue(await store.claim_task_run(self.db, 'TASK_1'))
        self.assertFalse(await store.claim_task_run(self.db, 'TASK_1'))
        task = await store.get_task(self.db, 'TASK_1')
        self.assertEqual(task['status'], 'submitted')
        self.assertFalse(task['result'])
        self.assertEqual(task['resultPath'], '')
        for status in ('queued', 'running'):
            await store.update_task(self.db, 'TASK_1', status=status)
            self.assertFalse(await store.claim_task_run(self.db, 'TASK_1'))

    async def test_missing_task_and_delete_cleanup(self):
        self.assertFalse(await store.claim_task_run(self.db, 'missing'))
        self.assertIsNone(await store.update_task(self.db, 'missing', status='running'))
        self.assertTrue(await store.delete_task(self.db, 'TASK_1'))
        self.assertEqual((await history.list_task_history(self.db, 'TASK_1'))['total'], 0)
        self.assertFalse(await store.delete_task(self.db, 'TASK_1'))

    async def test_history_endpoint_and_pagination_validation(self):
        import httpx
        from fastapi import FastAPI
        from config.get_db import get_db
        from module_admin.controller.algorithm_link_controller import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: self.db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/algorithm/task/history/TASK_1?pageNum=1&pageSize=10')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['data']['total'], 1)
            for query in ('pageNum=0', 'pageSize=0', 'pageSize=101'):
                invalid = await client.get('/algorithm/task/history/TASK_1?' + query)
                self.assertEqual(invalid.status_code, 422)
            missing = await client.get('/algorithm/task/history/missing')
            self.assertFalse(missing.json()['success'])

    async def test_only_missing_table_triggers_ddl(self):
        db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
        missing = ProgrammingError('SELECT', {}, Exception(1146, 'table missing'))
        db.execute.side_effect = [missing, None]
        await history.ensure_history_table(db)
        db.rollback.assert_awaited_once()
        db.commit.assert_awaited_once()
        self.assertIn('CREATE TABLE', str(db.execute.call_args_list[1].args[0]))
        denied = ProgrammingError('SELECT', {}, Exception(1142, 'permission denied'))
        db.execute.side_effect = denied
        with self.assertRaises(ProgrammingError):
            await history.ensure_history_table(db)

    async def test_run_endpoint_rejects_active_task_without_remote_submission(self):
        from module_admin.controller import algorithm_link_controller as controller

        await store.claim_task_run(self.db, 'TASK_1')
        with patch.object(controller, 'AlgorithmClient') as client:
            response = await controller.run_algorithm_task('TASK_1', self.db)
            self.assertFalse(json.loads(response.body)['success'])
            client.assert_not_called()


if __name__ == '__main__':
    unittest.main()
