from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, UniqueConstraint

from config.database import Base


class SysNoticeRead(Base):
    """通知公告阅读记录表。"""

    __tablename__ = 'sys_notice_read'
    __table_args__ = (
        UniqueConstraint('notice_id', 'reader_type', 'reader_key', name='uk_notice_reader'),
        {'comment': '通知公告阅读记录表'},
    )

    read_id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=True, comment='阅读记录ID')
    notice_id = Column(Integer, nullable=False, index=True, comment='公告ID')
    reader_type = Column(String(20), nullable=False, comment='阅读者类型（screen/user）')
    reader_key = Column(String(64), nullable=False, comment='阅读者标识')
    read_time = Column(DateTime, nullable=False, default=datetime.now, comment='阅读时间')
