from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.collection import Collection
from app.models.audio_file import AudioFile
from app.schemas.collection import CollectionCreate, CollectionRename, CollectionResponse

# 音频合集路由（路由前缀：/api/collections ）
router = APIRouter()

# 将 ORM 对象转换为 Pydantic 对象
def _to_response(col: Collection, db: Session) -> CollectionResponse:
    # 实时统计音频合集中的音频文件数量
    count = db.query(func.count(AudioFile.id)).filter(AudioFile.collection_id == col.id).scalar() or 0
    return CollectionResponse(
        id=col.id,
        name=col.name,
        created_at=col.created_at,
        audio_count=count,
    )

# 获取音频合集列表
@router.get("/", response_model=list[CollectionResponse])
def list_collections(db: Session = Depends(get_db)):
    # 查询所有音频合集，按创建时间排序
    cols = db.query(Collection).order_by(Collection.created_at).all()
    return [_to_response(c, db) for c in cols]

# 创建音频合集
@router.post("/", response_model=CollectionResponse, status_code=201)
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)):
    # 创建音频合集对象
    col = Collection(name=payload.name.strip())
    # 添加音频合集对象到数据库
    db.add(col)
    # 刷新数据库
    db.flush()
    # 刷新音频合集对象
    db.refresh(col)
    return _to_response(col, db)

# 重命名音频合集
@router.put("/{collection_id}", response_model=CollectionResponse)
def rename_collection(collection_id: int, payload: CollectionRename, db: Session = Depends(get_db)):
    # 获取音频合集对象
    col = db.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    # 修改音频合集对象
    col.name = payload.name.strip()
    # 刷新数据库
    db.flush()
    return _to_response(col, db)

# 删除音频合集
@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    # 获取音频合集对象
    col = db.get(Collection, collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    # 删除音频合集对象
    # audio_files.collection_id SET NULL via FK ondelete
    db.delete(col)
