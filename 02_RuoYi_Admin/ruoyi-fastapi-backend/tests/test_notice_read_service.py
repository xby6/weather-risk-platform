from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from module_admin.service.notice_read_service import NoticeReadService


class NoticeReadServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_attach_read_status_supports_paginated_camel_case_rows(self) -> None:
        read_time = datetime(2026, 7, 5, 18, 0, 0)
        rows = [{'noticeId': 1, 'noticeTitle': '公告一'}, {'noticeId': 2, 'noticeTitle': '公告二'}]
        with patch.object(
            NoticeReadService,
            'get_read_status_map',
            new=AsyncMock(return_value={2: read_time}),
        ):
            result = await NoticeReadService.attach_read_status(None, rows, 'user', '1')

        self.assertFalse(result[0]['isRead'])
        self.assertIsNone(result[0]['readTime'])
        self.assertTrue(result[1]['isRead'])
        self.assertEqual(result[1]['readTime'], read_time)

    def test_invalid_reader_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NoticeReadService._reader('unknown', '')


if __name__ == '__main__':
    unittest.main()
