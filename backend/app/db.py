from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

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
