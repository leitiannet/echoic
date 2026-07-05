from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.practice import WordScore

# 口语题目响应
class OralQuestionResponse(BaseModel):
    prompt        : str         # 题目提示
    reference_text: str | None  # 参考文本

# 口语练习响应
class OralAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id                 : int                     # 口语练习记录ID
    question_type      : str                     # 题目类型
    question_language  : str                     # 题目语言
    question_difficulty: str | None              # 题目难度
    question_prompt    : str                     # 题目提示
    question_reference : str | None              # 参考文本
    accuracy_score     : float | None            # 准确率
    fluency_score      : float | None            # 流利度
    completeness_score : float | None            # 完整度
    word_scores        : list[WordScore] | None  # 单词得分
    transcription      : str | None              # 转录
    llm_score          : float | None            # LLM得分
    llm_feedback       : str | None              # LLM反馈
    llm_highlights     : list[str] | None        # LLM高亮
    timer_secs         : int | None              # 计时秒数
    created_at         : datetime                # 创建时间

# 口语练习摘要
class OralAttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id                 : int           # 口语练习记录ID
    question_type      : str           # 题目类型
    question_language  : str           # 题目语言
    question_difficulty: str | None    # 题目难度
    question_prompt    : str           # 题目提示
    accuracy_score     : float | None  # 准确率
    fluency_score      : float | None  # 流利度
    llm_score          : float | None  # LLM得分
    timer_secs         : int | None    # 计时秒数
    created_at         : datetime      # 创建时间
