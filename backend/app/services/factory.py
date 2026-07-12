from functools import lru_cache
from app.config import settings
from app.services.asr.base import ASRService
from app.services.alignment.base import AlignmentService
from app.services.llm.base import LLMService
from app.services.scoring.base import ScoringService
from app.services.storage.base import StorageService
from app.services.tts.base import TTSService
from app.services.media.base import MediaService

# 获取语音识别服务
@lru_cache(maxsize=None)
def get_asr_service(language: str | None = None) -> ASRService:
    match settings.asr.backend:
        case "whisperx":
            from app.services.asr.whisperx import WhisperXASRService
            from app.config import WhisperXConfig
            if language is None or language == settings.asr.whisperx.language:
                return WhisperXASRService(settings.asr.whisperx)
            config = WhisperXConfig(
                model_size=settings.asr.whisperx.model_size,
                device=settings.asr.whisperx.device,
                compute_type=settings.asr.whisperx.compute_type,
                language=language,
                batch_size=settings.asr.whisperx.batch_size,
            )
            return WhisperXASRService(config)
        case _:
            raise ValueError(f"Unknown ASR backend: {settings.asr.backend}")

# 获取对齐服务
@lru_cache(maxsize=None)
def get_alignment_service(language: str | None = None) -> AlignmentService:
    match settings.alignment.backend:
        case "wav2vec2":
            from app.services.alignment.wav2vec2 import Wav2Vec2AlignmentService
            from app.config import Wav2Vec2AlignmentConfig
            if language is None or language == settings.alignment.wav2vec2.language:
                return Wav2Vec2AlignmentService(settings.alignment.wav2vec2)
            config = Wav2Vec2AlignmentConfig(
                model_id=settings.alignment.wav2vec2.model_id,
                device=settings.alignment.wav2vec2.device,
                language=language,
            )
            return Wav2Vec2AlignmentService(config)
        case _:
            raise ValueError(f"Unknown alignment backend: {settings.alignment.backend}")

# 获取评分服务
@lru_cache
def get_scoring_service() -> ScoringService:
    match settings.scoring.backend:
        case "phoneme":
            from app.services.scoring.phoneme import PhonemeScoringService
            return PhonemeScoringService(settings.scoring.phoneme)
        case _:
            raise ValueError(f"Unknown scoring backend: {settings.scoring.backend}")

# 获取大语音模型服务
@lru_cache
def get_llm_service() -> LLMService:
    match settings.llm.backend:
        case "openai":
            from app.services.llm.openai import OpenAILLMService
            return OpenAILLMService(settings.llm.openai)
        case "ollama":
            from app.services.llm.ollama import OllamaLLMService
            return OllamaLLMService(settings.llm.ollama)
        case _:
            raise ValueError(f"Unknown LLM backend: {settings.llm.backend}")

# 获取语音合成服务
@lru_cache
def get_tts_service() -> TTSService:
    match settings.tts.backend:
        case "espeak":
            from app.services.tts.espeak import EspeakTTSService
            return EspeakTTSService(settings.tts.espeak)
        case "edge-tts":
            from app.services.tts.edge_tts import EdgeTTSService
            return EdgeTTSService(settings.tts.edge_tts)
        case "pyttsx4":
            from app.services.tts.pyttsx4 import Pyttsx4TTSService
            return Pyttsx4TTSService(settings.tts.pyttsx4)
        case _:
            raise ValueError(f"Unknown TTS backend: {settings.tts.backend}")

# 获取媒体服务
@lru_cache
def get_media_service() -> MediaService:
    match settings.media.backend:
        case "local":
            from app.services.media.local import LocalMediaService
            return LocalMediaService(settings.media.local)
        case _:
            raise ValueError(f"Unknown media backend: {settings.media.backend}")

# 获取存储服务
@lru_cache
def get_storage_service(backend: str = "") -> StorageService:
    """
    Returns StorageService for the given backend name.
    Defaults to the configured active backend (used when saving new files).
    Pass record.storage_backend when reading/deleting existing files.
    """
    target = backend or settings.storage.backend
    match target:
        case "local":
            from app.services.storage.local import LocalStorageService
            return LocalStorageService(settings.storage)
        case _:
            raise ValueError(f"Unknown storage backend: {target}")
