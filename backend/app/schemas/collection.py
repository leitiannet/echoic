from datetime import datetime
from pydantic import BaseModel, ConfigDict


# 音频合集创建对象
class CollectionCreate(BaseModel):
    name: str # 音频合集名称


# 音频合集重命名对象
class CollectionRename(BaseModel):
    name: str # 音频合集名称


# 音频合集响应对象
class CollectionResponse(BaseModel):
    id         : int       # 音频合集 ID
    name       : str       # 音频合集名称
    created_at : datetime  # 音频合集创建时间
    audio_count: int = 0   # 音频合集中的音频文件数量

    model_config = ConfigDict(from_attributes=True)
