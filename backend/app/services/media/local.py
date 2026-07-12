import subprocess
from pathlib import Path

from app.config import LocalMediaConfig
from app.services.media.base import MediaError, MediaService

_VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".wmv"}
_PDF_SUFFIXES = {".pdf"}


def _subprocess_media_error(tool: str, exc: subprocess.CalledProcessError) -> MediaError:
    stderr = (exc.stderr or b"").decode(errors="replace").strip()
    detail = stderr.splitlines()[-1] if stderr else str(exc)
    if tool == "ffmpeg" and "does not contain any stream" in stderr.lower():
        return MediaError("Video contains no audio track")
    return MediaError(f"{tool} failed: {detail}")


class LocalMediaService(MediaService):
    """Local media conversion using ffmpeg and pypdf."""

    def __init__(self, config: LocalMediaConfig):
        self.config = config

    def media_kind(self, filename: str, content_type: str | None = None) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in _PDF_SUFFIXES or (content_type and "pdf" in content_type):
            return "pdf"
        if suffix in _VIDEO_SUFFIXES or (content_type and content_type.startswith("video/")):
            return "video"
        return "audio"

    def extract_audio(self, src_path: str, dst_path: str) -> None:
        self._extract_audio(src_path, dst_path)

    def _extract_audio(self, src_path: str, dst_path: str) -> None:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", src_path, "-vn", "-ac", "1", dst_path],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as e:
            raise MediaError("ffmpeg not found") from e
        except subprocess.CalledProcessError as e:
            raise _subprocess_media_error("ffmpeg", e) from e

    def extract_text(self, src_path: str, *, kind: str) -> str:
        if kind == "pdf":
            return self._extract_pdf_text(src_path)
        raise MediaError(f"extract_text not supported for {kind!r}")

    def _extract_pdf_text(self, src_path: str) -> str:
        from pypdf import PdfReader

        try:
            reader = PdfReader(src_path)
        except Exception as e:
            raise MediaError(f"Failed to read PDF: {e}") from e
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        if not text:
            raise MediaError("PDF contains no extractable text")
        return text

    def compress_audio(self, src_path: str, dst_path: str) -> None:
        self._compress_audio(src_path, dst_path)

    def _compress_audio(self, src_path: str, dst_path: str) -> None:
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ab", "64k", dst_path],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as e:
            raise MediaError("ffmpeg not found") from e
        except subprocess.CalledProcessError as e:
            raise _subprocess_media_error("ffmpeg", e) from e
