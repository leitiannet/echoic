from abc import ABC, abstractmethod


class MediaError(Exception):
    """Raised when video/PDF conversion fails."""


class MediaService(ABC):
    @abstractmethod
    def media_kind(self, filename: str, content_type: str | None = None) -> str:
        """Return 'audio', 'video', or 'pdf'."""

    @abstractmethod
    def extract_audio(self, src_path: str, dst_path: str) -> None:
        """Extract audio track from a video file."""

    @abstractmethod
    def extract_text(self, src_path: str, *, kind: str) -> str:
        """Extract text from a document file (pdf, word, …)."""

    @abstractmethod
    def compress_audio(self, src_path: str, dst_path: str) -> None:
        """Re-encode audio as 64 kbps mono MP3."""
