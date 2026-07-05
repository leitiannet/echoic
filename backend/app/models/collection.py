from datetime import datetime
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base, UTCDateTime

# 音频合集模型
class Collection(Base):
    # 表名
    __tablename__ = "collections"
    # 字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=datetime.utcnow)

    audio_files = relationship("AudioFile", back_populates="collection")
