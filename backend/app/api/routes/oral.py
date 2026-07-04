from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models.oral_attempt import OralAttempt
from app.schemas.oral import OralAttemptResponse, OralAttemptSummary, OralQuestionResponse
from app.services.factory import (
    get_alignment_service,
    get_asr_service,
    get_llm_service,
    get_scoring_service,
    get_storage_service,
)
from app.services.llm.base import LLMService
from app.services.scoring.base import ScoringService
from app.services.storage.base import StorageService

router = APIRouter()

QUESTION_TYPES = {"read_aloud", "situational", "monologue"}
DIFFICULTIES = {"beginner", "intermediate", "advanced"}


def _recording_key(filename: str) -> str:
    suffix = Path(filename).suffix or ".webm"
    return f"oral/{uuid4().hex}{suffix}"

# 生成题目（不落库）
@router.post("/questions/generate", response_model=OralQuestionResponse)
async def generate_question(
    question_type: str = Query(...),
    language: str = Query(...),
    difficulty: str = Query("intermediate"),
    topic: str | None = Query(None),
    llm: LLMService = Depends(get_llm_service),
):
    if question_type not in QUESTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown question type: {question_type}")
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=400, detail=f"Difficulty must be one of: {', '.join(DIFFICULTIES)}")
    # 调用 LLM 生成题目
    result = llm.generate_question(question_type, language, difficulty, topic)
    if not result.get("prompt"):
        raise HTTPException(status_code=502, detail="LLM failed to generate a question")
    return OralQuestionResponse(
        prompt=result["prompt"],
        reference_text=result.get("reference_text"),
    )


# 提交练习（上传录音、发音评分、 LLM 内容评分、落库）
@router.post("/attempts", response_model=OralAttemptResponse)
async def submit_attempt(
    question_type: str = Form(...),
    question_language: str = Form(...),
    question_prompt: str = Form(...),
    question_difficulty: str | None = Form(None),
    question_reference: str | None = Form(None),
    timer_secs: int | None = Form(None),
    file: UploadFile = File(...), # 上传录音
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    scoring: ScoringService = Depends(get_scoring_service),
    llm: LLMService = Depends(get_llm_service),
):
    # 保存录音
    key = _recording_key(file.filename or "recording.bin")
    storage.save(await file.read(), key)
    recording_path = storage.get_absolute_path(key)

    alignment = get_alignment_service(question_language)
    asr = get_asr_service(question_language)
    # 创建口语练习模型
    attempt = OralAttempt(
        question_type=question_type,
        question_language=question_language,
        question_difficulty=question_difficulty,
        question_prompt=question_prompt,
        question_reference=question_reference,
        storage_backend=settings.storage.backend,
        recording_path=key,
        timer_secs=timer_secs,
    )

    if question_type == "read_aloud" and question_reference:
        # 对齐
        aligned_words = alignment.align(recording_path, question_reference)
        # 评分
        result = scoring.score(recording_path, question_reference, aligned_words, language=question_language)
        attempt.accuracy_score = result.accuracy_score
        attempt.fluency_score = result.fluency_score
        attempt.completeness_score = result.completeness_score
        attempt.word_scores = [ws.model_dump() for ws in result.word_scores]
    else:
        # 转录
        sentences = asr.transcribe(recording_path)
        transcript = " ".join(s.text for s in sentences).strip()
        attempt.transcription = transcript

        if transcript:
            # 对齐
            aligned_words = alignment.align(recording_path, transcript)
            # 评分
            result = scoring.score(recording_path, transcript, aligned_words, language=question_language)
            attempt.accuracy_score = result.accuracy_score
            attempt.fluency_score = result.fluency_score
            attempt.completeness_score = result.completeness_score
            attempt.word_scores = [ws.model_dump() for ws in result.word_scores]
        # 调用 LLM 内容评分
        llm_result = llm.score_oral_response(
            question_type=question_type,
            prompt=question_prompt,
            transcription=transcript or "",
            context=question_reference,
        )
        attempt.llm_score = llm_result.get("score")
        attempt.llm_feedback = llm_result.get("feedback")
        attempt.llm_highlights = llm_result.get("highlights")
    # 落库
    db.add(attempt)
    db.flush()
    db.refresh(attempt)
    return attempt

# 查询练习列表
@router.get("/attempts", response_model=list[OralAttemptSummary])
def list_attempts(
    question_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(OralAttempt)
    if question_type:
        q = q.filter(OralAttempt.question_type == question_type)
    return q.order_by(OralAttempt.created_at.desc()).limit(limit).all()

# 查询练习详情
@router.get("/attempts/{attempt_id}", response_model=OralAttemptResponse)
def get_attempt(attempt_id: int, db: Session = Depends(get_db)):
    attempt = db.get(OralAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt

# 回放练习录音
@router.get("/attempts/{attempt_id}/stream")
def stream_attempt(attempt_id: int, db: Session = Depends(get_db)):
    attempt = db.get(OralAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found")
    storage = get_storage_service(attempt.storage_backend)
    path = storage.get_absolute_path(attempt.recording_path)
    # 返回录音文件
    return FileResponse(path)
