import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.audio_file import AudioFile
from app.models.practice_record import PracticeRecord
from app.config import settings
from app.schemas.audio import AudioFileCreate, AudioFileResponse, WordPhoneme
from app.services.asr.base import ASRService
from app.services.factory import get_asr_service, get_llm_service, get_scoring_service, get_storage_service
from app.services.llm.base import LLMService
from app.services.scoring.base import ScoringService
from app.services.storage.base import StorageService
from app.services.factory import get_media_service, get_tts_service
from app.services.media.base import MediaError, MediaService
from app.services.tts.base import TTSError, TTSService

# 音频素材路由（路由前缀：/api/audio ）
router = APIRouter()

# 下载远程音频链接，返回 (内容, Content-Type)
async def _download_url(url: str) -> tuple[bytes, str | None]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Echoic/1.0)",
        "Accept": "*/*",
    }
    host = urlparse(url).netloc
    if "voanews" in host:
        headers["Referer"] = "https://learningenglish.voanews.com/"
    async with httpx.AsyncClient(follow_redirects=True, timeout=300.0, headers=headers) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            raw_type = response.headers.get("content-type")
            content_type = raw_type.split(";")[0].strip().lower() if raw_type else None
            return await response.aread(), content_type

# 生成音频文件存储键（使用 uuid4 生成唯一标识，并添加后缀）
def _audio_key(filename: str, *, compressed: bool = False, suffix: str | None = None) -> str:
    if compressed:
        ext = ".mp3"
    elif suffix is not None:
        ext = suffix
    else:
        ext = Path(filename).suffix
    return f"audio/{uuid4().hex}{ext}"

# 压缩音频文件（使用 ffmpeg 压缩为 64 kbps mono MP3 ，删除原始文件）
def _compress_audio(storage: StorageService, media: MediaService, key: str) -> str:
    """Re-encode stored file as 64 kbps mono MP3. Returns new key."""
    src = storage.get_absolute_path(key)
    new_key = _audio_key("compressed.mp3", compressed=True)
    dst = storage.get_absolute_path(new_key)
    media.compress_audio(src, dst)
    try:
        # 删除原始文件
        storage.delete(key)
    except Exception:
        pass
    return new_key

# 转换为音频文件
def _convert_to_audio(
    storage: StorageService,
    media: MediaService,
    tts: TTSService,
    key: str,
    *,
    kind: str,
    language: str,
) -> str:
    src = storage.get_absolute_path(key)
    if kind == "video":
        new_key = _audio_key("extracted.wav")
        media.extract_audio(src, storage.get_absolute_path(new_key))
        return new_key
    if kind == "pdf":
        text = media.extract_text(src, kind=kind)
        suffix = ".mp3" if settings.tts.backend == "edge-tts" else ".wav"
        new_key = _audio_key("tts", suffix=suffix)
        tts.synthesize(text, storage.get_absolute_path(new_key), language=language)
        return new_key
    return key

# 持久化音频文件
def _persist_audio_file(
    db: Session,
    *,
    title: str,
    source_type: str,
    key: str,
    sentences,
    language: str = "en",
    collection_id: int | None = None,
) -> AudioFile:
    audio_file = AudioFile(
        title=title,
        source_type=source_type,
        language=language,
        collection_id=collection_id,
        storage_backend=settings.storage.backend,
        file_path=key,
        sentences=[sentence.model_dump() for sentence in sentences],
    )
    db.add(audio_file)
    db.flush()
    db.refresh(audio_file)
    return audio_file

# 上传本地音频文件
@router.post("/upload", response_model=AudioFileResponse)
async def upload_audio(
    file: UploadFile = File(...),
    compress: bool = Query(False),
    collection_id: int | None = Query(None),
    db: Session = Depends(get_db),
    asr: ASRService = Depends(get_asr_service),
    storage: StorageService = Depends(get_storage_service),
    media: MediaService = Depends(get_media_service),
    tts: TTSService = Depends(get_tts_service),
):
    filename = file.filename or "upload.bin"
    # 生成音频文件存储键
    key = _audio_key(filename)
    # 保存音频文件 // 原始文件存储
    storage.save(await file.read(), key)
    # 其他格式文件转为音频文件
    kind = media.media_kind(filename, file.content_type)
    if kind != "audio":
        original_key = key
        try:
            key = await asyncio.to_thread(
                _convert_to_audio, storage, media, tts, key,
                kind=kind,
                language=settings.asr.whisperx.language,
            )
        except (MediaError, TTSError) as e:
            try:
                storage.delete(key)
            except Exception:
                pass
            raise HTTPException(status_code=400, detail=str(e)) from e
        try:
            storage.delete(original_key)
        except Exception:
            pass
    # 识别音频文件
    sentences = await asyncio.to_thread(asr.transcribe, storage.get_absolute_path(key))
    # 压缩音频文件（先用原始音频做识别，再按需压缩）
    if compress:
        try:
            key = await asyncio.to_thread(_compress_audio, storage, media, key)
        except MediaError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    title = Path(file.filename or "upload").stem or "upload"
    # 持久化音频文件
    return _persist_audio_file(
        db,
        title=title, # 原始文件名作为标题
        source_type="upload", # 上传类型
        key=key,
        sentences=sentences,
        language=settings.asr.whisperx.language,
        collection_id=collection_id,
    )

# 导入远程音频链接
@router.post("/from-url")
async def import_from_url(
    payload: AudioFileCreate,
    compress: bool = Query(False),
    db: Session = Depends(get_db),
    asr: ASRService = Depends(get_asr_service),
    storage: StorageService = Depends(get_storage_service),
    media: MediaService = Depends(get_media_service),
    tts: TTSService = Depends(get_tts_service),
):
    if not payload.url:
        raise HTTPException(status_code=400, detail="url is required")

    def event(data: dict) -> str:
        return f"data: {json.dumps(data)}\n\n"

    async def generate():
        try:
            yield event({"step": "downloading"})
            try:
                # 下载远程音频链接
                audio_bytes, content_type = await _download_url(payload.url)
            except httpx.HTTPError as e:
                yield event({"step": "error", "message": str(e)})
                return

            yield event({"step": "saving"})
            filename = Path(urlparse(payload.url).path).name or "imported.mp3"
            key = _audio_key(filename)
            # 保存音频文件 // 原始文件存储
            storage.save(audio_bytes, key)
            kind = media.media_kind(filename, content_type)
            if kind != "audio":
                yield event({"step": "converting"})
                original_key = key
                try:
                    key = await asyncio.to_thread(
                        _convert_to_audio, storage, media, tts, key,
                        kind=kind,
                        language=settings.asr.whisperx.language,
                    )
                except (MediaError, TTSError) as e:
                    try:
                        storage.delete(key)
                    except Exception:
                        pass
                    yield event({"step": "error", "message": str(e)})
                    return
                try:
                    storage.delete(original_key)
                except Exception:
                    pass

            yield event({"step": "transcribing"})
            sentences = await asyncio.to_thread(asr.transcribe, storage.get_absolute_path(key))

            # 压缩音频文件（先识别，再按需压缩）
            if compress:
                yield event({"step": "compressing"})
                try:
                    key = await asyncio.to_thread(_compress_audio, storage, media, key)
                except MediaError as e:
                    yield event({"step": "error", "message": str(e)})
                    return

            title = payload.title or Path(filename).stem or urlparse(payload.url).hostname or "imported"
            audio_file = _persist_audio_file(
                db, 
                title=title, 
                source_type="url", # 远程 URL 类型
                key=key,
                sentences=sentences, 
                language=settings.asr.whisperx.language,
                collection_id=payload.collection_id,
            )
            result = AudioFileResponse.model_validate(audio_file)
            yield event({"step": "done", "result": result.model_dump(mode="json")})
        except Exception as e:
            yield event({"step": "error", "message": str(e)})

    return StreamingResponse(generate(), media_type="text/event-stream")

# 获取音频文件列表
@router.get("/", response_model=list[AudioFileResponse])
async def list_audio_files(db: Session = Depends(get_db)):
    from sqlalchemy import func as sa_func

    rows = (
        db.query(AudioFile, sa_func.count(PracticeRecord.id).label("practice_count"))
        .outerjoin(PracticeRecord, PracticeRecord.audio_file_id == AudioFile.id)
        .group_by(AudioFile.id)
        .order_by(AudioFile.created_at.desc())
        .all()
    )
    result = []
    for audio_file, count in rows:
        data = AudioFileResponse.model_validate(audio_file)
        data.practice_count = count
        result.append(data)
    return result

# 获取音频文件详情
@router.get("/{audio_file_id}", response_model=AudioFileResponse)
async def get_audio_file(audio_file_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import func as sa_func
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    count_rows = (
        db.query(PracticeRecord.sentence_index, sa_func.count(PracticeRecord.id))
        .filter(PracticeRecord.audio_file_id == audio_file_id)
        .group_by(PracticeRecord.sentence_index)
        .all()
    )
    count_map = {idx: cnt for idx, cnt in count_rows}
    response = AudioFileResponse.model_validate(audio_file)
    if response.sentences:
        for s in response.sentences:
            s.practice_count = count_map.get(s.index, 0)
    return response

# 获取句子字典
def _get_sentence_dict(audio_file: AudioFile, sentence_index: int) -> dict:
    sentences = audio_file.sentences or []
    if sentence_index < 0 or sentence_index >= len(sentences):
        raise HTTPException(status_code=404, detail="sentence not found")
    return sentences[sentence_index]

# 更新句子字段
def _update_sentence_field(db: Session, audio_file: AudioFile, sentence_index: int, **fields) -> None:
    sentences = [dict(s) for s in (audio_file.sentences or [])]
    sentences[sentence_index].update(fields)
    audio_file.sentences = sentences
    db.commit()

# 切换句子掌握状态
@router.post("/{audio_file_id}/sentence/{sentence_index}/master")
async def toggle_master(
    audio_file_id: int,
    sentence_index: int,
    db: Session = Depends(get_db),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    sentence = _get_sentence_dict(audio_file, sentence_index)
    new_val = not sentence.get("mastered", False)
    _update_sentence_field(db, audio_file, sentence_index, mastered=new_val)
    return {"mastered": new_val}

# 切换句子收藏状态
@router.post("/{audio_file_id}/sentence/{sentence_index}/bookmark")
async def toggle_bookmark(
    audio_file_id: int,
    sentence_index: int,
    db: Session = Depends(get_db),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    sentence = _get_sentence_dict(audio_file, sentence_index)
    new_val = not sentence.get("bookmarked", False)
    _update_sentence_field(db, audio_file, sentence_index, bookmarked=new_val)
    return {"bookmarked": new_val}

# 获取句子音素
@router.get("/{audio_file_id}/sentence/{sentence_index}/phonemes", response_model=list[WordPhoneme])
async def get_sentence_phonemes(
    audio_file_id: int,
    sentence_index: int,
    refresh: bool = Query(False),
    db: Session = Depends(get_db),
    scoring: ScoringService = Depends(get_scoring_service),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    sentence = _get_sentence_dict(audio_file, sentence_index)
    if not refresh and (cached := sentence.get("word_phonemes")):
        return [WordPhoneme(**p) for p in cached]
    words = [w["word"] for w in (sentence.get("words") or []) if w.get("word")]
    if not words:
        words = str(sentence.get("text", "")).split()
    ipa_list = scoring.phonemize_words(words)
    result = [WordPhoneme(word=w, ipa=p) for w, p in zip(words, ipa_list)]
    _update_sentence_field(db, audio_file, sentence_index, word_phonemes=[r.model_dump() for r in result])
    return result

# 分析句子
@router.post("/{audio_file_id}/sentence/{sentence_index}/analyze")
async def analyze_sentence(
    audio_file_id: int,
    sentence_index: int,
    lang: str = Query("zh-CN"),
    db: Session = Depends(get_db),
    llm: LLMService = Depends(get_llm_service),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    sentence = _get_sentence_dict(audio_file, sentence_index)
    if sentence.get("analysis"):
        return {"analysis": sentence["analysis"]}
    if settings.llm.backend == "openai" and not settings.llm.openai.api_key:
        raise HTTPException(status_code=503, detail="LLM not configured")
    analysis = llm.analyze(str(sentence.get("text", "")), reply_lang=lang, source_lang=audio_file.language or "en")
    _update_sentence_field(db, audio_file, sentence_index, analysis=analysis)
    return {"analysis": analysis}

# 流式播放音频文件
@router.get("/{audio_file_id}/stream")
async def stream_audio_file(audio_file_id: int, db: Session = Depends(get_db)):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    storage = get_storage_service(audio_file.storage_backend)
    path = storage.get_absolute_path(audio_file.file_path)
    return FileResponse(path)


class AudioFileUpdate(BaseModel):
    title: str | None = None
    language: str | None = None

# 更新音频文件
@router.patch("/{audio_file_id}", response_model=AudioFileResponse)
async def update_audio_file(
    audio_file_id: int,
    payload: AudioFileUpdate,
    db: Session = Depends(get_db),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    if payload.title is not None:
        audio_file.title = payload.title
    if payload.language is not None:
        audio_file.language = payload.language
    db.commit()
    db.refresh(audio_file)
    return audio_file

# 重新运行语音识别
@router.post("/{audio_file_id}/asr", response_model=AudioFileResponse)
async def rerun_asr(
    audio_file_id: int,
    db: Session = Depends(get_db),
    asr: ASRService = Depends(get_asr_service),
    storage: StorageService = Depends(get_storage_service),
):
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    path = storage.get_absolute_path(audio_file.file_path)
    sentences = await asyncio.to_thread(asr.transcribe, path)
    audio_file.sentences = [s.model_dump() for s in sentences]
    db.commit()
    db.refresh(audio_file)
    return audio_file

# 删除音频文件
@router.delete("/{audio_file_id}", status_code=204)
async def delete_audio_file(
    audio_file_id: int,
    db: Session = Depends(get_db),
):
    # 获取音频文件对象
    audio_file = db.get(AudioFile, audio_file_id)
    if audio_file is None:
        raise HTTPException(status_code=404, detail="audio file not found")
    storage = get_storage_service(audio_file.storage_backend)
    try:
        # 删除音频文件
        storage.delete(audio_file.file_path)
    except Exception:
        pass
    # 删除练习记录
    db.query(PracticeRecord).filter(PracticeRecord.audio_file_id == audio_file_id).delete()
    # 删除音频文件对象
    db.delete(audio_file)
    db.commit()


