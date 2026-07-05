from datetime import datetime
from pydantic import BaseModel, ConfigDict

# 单词得分
class WordScore(BaseModel):
    word             : str               # 单词
    accuracy_score   : float             # 准确率
    expected_phonemes: str               # 预期音标
    actual_phonemes  : str               # 实际音标
    phoneme_scores   : list[float] = []  # per-phoneme score for each char in expected_phonemes (stress markers excluded)

# 跟读练习记录响应对象
class PracticeRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id                : int                     # 跟读练习记录ID
    audio_file_id     : int                     # 音频文件ID
    sentence_index    : int                     # 句子索引
    sentence_text     : str                     # 句子文本
    accuracy_score    : float | None            # 准确率
    fluency_score     : float | None            # 流利度
    completeness_score: float | None            # 完整度
    word_scores       : list[WordScore] | None  # 单词得分
    created_at        : datetime                # 创建时间

# 热力图条目
class HeatmapEntry(BaseModel):
    date     : str           # YYYY-MM-DD
    count    : int           # 练习次数
    avg_score: float | None  # 平均得分
