import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.config import EdgeTTSConfig
from app.services.tts.base import TTSError, TTSService


def _run_async(coro) -> None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
    else:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, coro).result()


class EdgeTTSService(TTSService):
    def __init__(self, config: EdgeTTSConfig):
        self.config = config

    def synthesize(self, text: str, output_path: str, *, language: str = "en") -> None:
        if not text.strip():
            raise TTSError("Text is empty")

        voice = self.config.voices.get(language, language)

        async def _run() -> None:
            import edge_tts

            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)

        try:
            _run_async(_run())
        except ImportError as e:
            raise TTSError("edge-tts not installed") from e
        except Exception as e:
            raise TTSError(f"edge-tts failed: {e}") from e
