from app.config import Pyttsx4TTSConfig
from app.services.tts.base import TTSError, TTSService


class Pyttsx4TTSService(TTSService):
    def __init__(self, config: Pyttsx4TTSConfig):
        self.config = config

    def synthesize(self, text: str, output_path: str, *, language: str = "en") -> None:
        if not text.strip():
            raise TTSError("Text is empty")

        try:
            import pyttsx4
        except ImportError as e:
            raise TTSError("pyttsx4 not installed") from e

        try:
            engine = pyttsx4.init() if not self.config.engine else pyttsx4.init(self.config.engine)
            if voice_id := self.config.voices.get(language):
                engine.setProperty("voice", voice_id)
            engine.save_to_file(text, output_path)
            engine.runAndWait()
        except Exception as e:
            raise TTSError(f"pyttsx4 failed: {e}") from e
