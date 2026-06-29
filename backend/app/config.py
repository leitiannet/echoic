from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── ASR ──────────────────────────────────────────────────────────────────────

class WhisperXConfig(BaseModel):
    model_size: str = "base"        # tiny / base / small / medium / large-v2
    device: str = "cpu"             # cpu / cuda
    compute_type: str = "int8"      # int8 / float16 / float32
    language: str = "en"
    batch_size: int = 16


class ASRConfig(BaseModel):
    backend: str = "whisperx"       # whisperx | (future: assemblyai, deepgram …)
    whisperx: WhisperXConfig = WhisperXConfig()


# ── Alignment ─────────────────────────────────────────────────────────────────

class Wav2Vec2AlignmentConfig(BaseModel):
    model_id: str = "facebook/wav2vec2-base-960h"
    device: str = "cpu"
    language: str = "en"


class AlignmentConfig(BaseModel):
    backend: str = "wav2vec2"       # wav2vec2 | (future: mfa …)
    wav2vec2: Wav2Vec2AlignmentConfig = Wav2Vec2AlignmentConfig()


# ── Scoring ───────────────────────────────────────────────────────────────────

class PhonemeScoringConfig(BaseModel):
    # wav2vec2 model for phoneme recognition
    phoneme_model_id: str = "facebook/wav2vec2-lv-60-espeak-cv-ft"
    device: str = "cpu"
    language: str = "en-us"          # espeak language code
    # weights for the three dimensions
    accuracy_weight: float = 0.5
    fluency_weight: float = 0.3
    completeness_weight: float = 0.2


class ScoringConfig(BaseModel):
    backend: str = "phoneme"        # phoneme | (future: speechbrain …)
    phoneme: PhonemeScoringConfig = PhonemeScoringConfig()


# ── LLM ──────────────────────────────────────────────────────────────────────

class OpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"


class OllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3"
    num_ctx: int = 512          # context window; increase to 4096+ if think=True
    think: bool = False         # enable qwen3.5 thinking mode (slower, higher quality)


class LLMConfig(BaseModel):
    backend: str = "openai"
    openai: OpenAIConfig = OpenAIConfig()
    ollama: OllamaConfig = OllamaConfig()


# ── Storage ───────────────────────────────────────────────────────────────────

class StorageConfig(BaseModel):
    backend: str = "local"          # local | (future: s3 …)
    local_dir: str = "storage"
    # S3 config placeholder
    s3_bucket: str = ""
    s3_prefix: str = "echoic/"


# ── Top-level settings ────────────────────────────────────────────────────────

class Settings(BaseSettings):
    # 固定名称 model_config，值为 SettingsConfigDict()
    model_config = SettingsConfigDict(
        extra="ignore",  # 忽略 .env 文件中第三方库的变量
        env_file=".env",  # 指定 .env 文件路径
        env_nested_delimiter="__",  # e.g. ASR__BACKEND=whisperx
    )
    # 定义配置字段
    database_url: str = "postgresql://echoic:echoic@localhost:5432/echoic"
    cors_origins: list[str] = ["http://localhost:5173"]

    asr: ASRConfig = ASRConfig()
    alignment: AlignmentConfig = AlignmentConfig()
    scoring: ScoringConfig = ScoringConfig()
    storage: StorageConfig = StorageConfig()
    llm: LLMConfig = LLMConfig()


# ── Load settings ───────────────────────────────────────────────────────────


def _is_macos() -> bool:
    import platform
    return platform.system() == "Darwin"


def _cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


def _resolve_device(requested: str) -> str:
    device = requested.lower().strip()

    if device == "mps" and not _is_macos():
        return "cpu"

    if device == "cuda" and not _cuda_available():
        return "cpu"

    return device

# 加载 .env 文件到 os.environ , 用于第三方库（huggingface_hub, phonemizer）
def _load_dotenv() -> None:
    from dotenv import load_dotenv
    load_dotenv(".env", override=False)


def _load_settings() -> Settings:
    _load_dotenv()
    s = Settings()
    s.asr.whisperx.device = _resolve_device(s.asr.whisperx.device)
    if s.asr.whisperx.device == "mps":
        s.asr.whisperx.device = "cpu"
    s.alignment.wav2vec2.device = _resolve_device(s.alignment.wav2vec2.device)
    s.scoring.phoneme.device = _resolve_device(s.scoring.phoneme.device)
    return s


settings = _load_settings()
