from datetime import datetime
from pydantic import BaseModel, ConfigDict, computed_field


# 单词时间戳
class WordTimestamp(BaseModel):
    word : str    # 单词
    start: float  # 开始时间
    end  : float  # 结束时间


# 单词音标
class WordPhoneme(BaseModel):
    word: str  # 单词
    ipa : str  # 音标


# 句子
class Sentence(BaseModel):
    index         : int                  # 句子索引
    text          : str                  # 句子文本
    start         : float                # 开始时间
    end           : float                # 结束时间
    words         : list[WordTimestamp]  # 单词时间戳
    analysis      : str | None = None    # 分析
    bookmarked    : bool = False         # 是否收藏
    mastered      : bool = False         # 是否掌握
    practice_count: int = 0              # 练习次数


# 音频文件创建
class AudioFileCreate(BaseModel):
    title        : str | None = None  # 标题
    url          : str | None = None  # 链接
    collection_id: int | None = None  # 合集ID


# 音频文件响应
class AudioFileResponse(BaseModel):
    id            : int                    # 音频文件ID
    title         : str                    # 标题
    source_type   : str                    # 来源类型
    language      : str                    # 语言
    collection_id : int | None = None      # 合集ID
    sentences     : list[Sentence] | None  # 句子
    practice_count: int = 0                # 练习次数
    created_at    : datetime               # 创建时间

    @computed_field
    @property
    def duration(self) -> float | None:
        if self.sentences:
            return self.sentences[-1].end
        return None

    model_config = ConfigDict(from_attributes=True)
