from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from module_admin.service import algorithm_model_store


class FakeResult:
    def __init__(self, rows=None, row=None, rowcount=1):
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


class FakeDb:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.statements = []
        self.commit = AsyncMock()

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), params or {}))
        return self.results.pop(0) if self.results else FakeResult()


class AlgorithmModelSoftDeleteTest(unittest.IsolatedAsyncioTestCase):
    async def test_status_update_persists_disabled(self):
        db = FakeDb([FakeResult(rowcount=1)])
        get_model = AsyncMock(
            side_effect=[
                {"id": "6", "status": "enabled"},
                {"id": "6", "status": "disabled"},
            ]
        )
        with patch.object(algorithm_model_store, "get_model", get_model):
            model = await algorithm_model_store.update_model_status(db, 6, "disabled")

        self.assertEqual(model["status"], "disabled")
        self.assertEqual(db.statements[0][1]["status"], "disabled")
        db.commit.assert_awaited_once()

    async def test_delete_marks_record_deleted_instead_of_removing_it(self):
        db = FakeDb([FakeResult(rowcount=1)])
        with (
            patch.object(algorithm_model_store, "get_model", AsyncMock(return_value={"id": "7", "serverId": "1"})),
            patch.object(algorithm_model_store, "_refresh_server_model_count", AsyncMock()),
        ):
            deleted = await algorithm_model_store.delete_model(db, 7)

        self.assertTrue(deleted)
        sql = db.statements[0][0].upper()
        self.assertIn("UPDATE ALGORITHM_MODEL", sql)
        self.assertIn("STATUS = 'DELETED'", sql)
        self.assertNotIn("DELETE FROM", sql)
        db.commit.assert_awaited_once()

    async def test_list_excludes_deleted_records(self):
        db = FakeDb([FakeResult(rows=[])])
        await algorithm_model_store.list_models(db)
        self.assertIn("<> 'deleted'", db.statements[0][0])

    async def test_sync_does_not_restore_a_deleted_record(self):
        existing = SimpleNamespace(_mapping={"id": 9, "status": "deleted"})
        db = FakeDb([FakeResult(row=existing)])
        with (
            patch.object(algorithm_model_store, "_find_server_id", AsyncMock(return_value=1)),
            patch.object(
                algorithm_model_store,
                "get_model",
                AsyncMock(return_value={"id": "9", "algorithmId": "deleted-model", "status": "deleted"}),
            ),
        ):
            model = await algorithm_model_store.create_model(
                db,
                {
                    "serverId": 1,
                    "algorithmId": "deleted-model",
                    "algorithmName": "Deleted model",
                    "status": "enabled",
                    "preserveLocalStatus": True,
                },
            )

        self.assertEqual(model["status"], "deleted")
        self.assertEqual(len(db.statements), 1)
        db.commit.assert_not_awaited()

    async def test_sync_does_not_restore_a_disabled_record(self):
        existing = SimpleNamespace(_mapping={"id": 10, "status": "disabled"})
        db = FakeDb([FakeResult(row=existing)])
        with (
            patch.object(algorithm_model_store, "_find_server_id", AsyncMock(return_value=1)),
            patch.object(
                algorithm_model_store,
                "get_model",
                AsyncMock(return_value={"id": "10", "algorithmId": "disabled-model", "status": "disabled"}),
            ),
        ):
            model = await algorithm_model_store.create_model(
                db,
                {
                    "serverId": 1,
                    "algorithmId": "disabled-model",
                    "algorithmName": "Disabled model",
                    "status": "enabled",
                    "preserveLocalStatus": True,
                },
            )

        self.assertEqual(model["status"], "disabled")
        self.assertEqual(len(db.statements), 1)
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
