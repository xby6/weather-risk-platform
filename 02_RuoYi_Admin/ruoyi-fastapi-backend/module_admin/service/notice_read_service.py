from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.entity.do.notice_do import SysNotice
from module_admin.entity.do.notice_read_do import SysNoticeRead


class NoticeReadService:
    """公告阅读状态服务。"""

    @staticmethod
    def _reader(reader_type: str, reader_key: str) -> tuple[str, str]:
        normalized_type = str(reader_type or '').strip().lower()[:20]
        normalized_key = str(reader_key or '').strip()[:64]
        if normalized_type not in {'screen', 'user'} or not normalized_key:
            raise ValueError('公告阅读者标识无效')
        return normalized_type, normalized_key

    @classmethod
    async def get_read_status_map(
        cls,
        query_db: AsyncSession,
        notice_ids: list[int],
        reader_type: str,
        reader_key: str,
    ) -> dict[int, datetime]:
        if not notice_ids:
            return {}
        reader_type, reader_key = cls._reader(reader_type, reader_key)
        try:
            result = await query_db.execute(
                select(SysNoticeRead.notice_id, SysNoticeRead.read_time).where(
                    SysNoticeRead.notice_id.in_(notice_ids),
                    SysNoticeRead.reader_type == reader_type,
                    SysNoticeRead.reader_key == reader_key,
                )
            )
        except SQLAlchemyError:
            return {}
        return {int(row.notice_id): row.read_time for row in result.all()}

    @classmethod
    async def get_unread_count(
        cls,
        query_db: AsyncSession,
        reader_type: str,
        reader_key: str,
    ) -> int:
        reader_type, reader_key = cls._reader(reader_type, reader_key)
        try:
            result = await query_db.execute(
                select(func.count(SysNotice.notice_id))
                .outerjoin(
                    SysNoticeRead,
                    and_(
                        SysNoticeRead.notice_id == SysNotice.notice_id,
                        SysNoticeRead.reader_type == reader_type,
                        SysNoticeRead.reader_key == reader_key,
                    ),
                )
                .where(SysNotice.status == '0', SysNoticeRead.read_id.is_(None))
            )
        except SQLAlchemyError:
            return -1
        return int(result.scalar() or 0)

    @classmethod
    async def mark_read(
        cls,
        query_db: AsyncSession,
        notice_id: int,
        reader_type: str,
        reader_key: str,
    ) -> datetime:
        reader_type, reader_key = cls._reader(reader_type, reader_key)
        notice = (
            await query_db.execute(
                select(SysNotice.notice_id).where(SysNotice.notice_id == notice_id, SysNotice.status == '0')
            )
        ).scalar_one_or_none()
        if notice is None:
            raise ValueError('公告不存在或已关闭')

        read_time = datetime.now()
        record = (
            await query_db.execute(
                select(SysNoticeRead).where(
                    SysNoticeRead.notice_id == notice_id,
                    SysNoticeRead.reader_type == reader_type,
                    SysNoticeRead.reader_key == reader_key,
                )
            )
        ).scalars().first()
        if record:
            record.read_time = read_time
        else:
            query_db.add(
                SysNoticeRead(
                    notice_id=notice_id,
                    reader_type=reader_type,
                    reader_key=reader_key,
                    read_time=read_time,
                )
            )
        await query_db.commit()
        return read_time

    @classmethod
    async def attach_read_status(
        cls,
        query_db: AsyncSession,
        rows: list[Any],
        reader_type: str,
        reader_key: str,
    ) -> list[Any]:
        def notice_id_of(row: Any) -> int | None:
            value = row.get('noticeId', row.get('notice_id')) if isinstance(row, dict) else getattr(row, 'notice_id', None)
            return int(value) if value is not None else None

        notice_ids = [notice_id for row in rows if (notice_id := notice_id_of(row)) is not None]
        status_map = await cls.get_read_status_map(query_db, notice_ids, reader_type, reader_key)
        for row in rows:
            notice_id = notice_id_of(row)
            if isinstance(row, dict):
                row['isRead'] = notice_id in status_map
                row['readTime'] = status_map.get(notice_id)
            else:
                setattr(row, 'is_read', notice_id in status_map)
                setattr(row, 'read_time', status_map.get(notice_id))
        return rows
