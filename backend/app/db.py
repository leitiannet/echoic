from datetime import timezone
from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

class UTCDateTime(TypeDecorator):
    """Naive UTC 存库，读出补 timezone.utc → API 输出带 Z 的 ISO 8601。

    无时区字符串会被前端当本地时间解析（东八区偏差8小时）；不改库表结构。
    """
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

# 创建引擎（同步）
engine = create_engine(settings.database_url)
# 创建会话生成器（同步）
SessionLocal = sessionmaker(bind=engine)

# 模型基类，空基类统一管理全项目模型元数据（工程化最佳实践）
class Base(DeclarativeBase):
    pass


# 创建/销毁会话
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
