import subprocess
import tempfile
from pathlib import Path

from app.config import EspeakTTSConfig
from app.services.tts.base import TTSError, TTSService


def _subprocess_error(tool: str, exc: subprocess.CalledProcessError) -> TTSError:
    stderr = (exc.stderr or b"").decode(errors="replace").strip()
    detail = stderr.splitlines()[-1] if stderr else str(exc)
    return TTSError(f"{tool} failed: {detail}")


class EspeakTTSService(TTSService):
    def __init__(self, config: EspeakTTSConfig):
        self.config = config

    def synthesize(self, text: str, output_path: str, *, language: str = "en") -> None:
        if not text.strip():
            raise TTSError("Text is empty")

        voice = self.config.voices.get(language, language)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tf:
            tf.write(text)
            txt_path = tf.name

        try:
            subprocess.run(
                ["espeak-ng", "-v", voice, "-w", output_path, "-f", txt_path],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as e:
            raise TTSError("espeak-ng not found") from e
        except subprocess.CalledProcessError as e:
            raise _subprocess_error("espeak-ng", e) from e
        finally:
            Path(txt_path).unlink(missing_ok=True)
