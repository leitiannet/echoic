from abc import ABC, abstractmethod


class TTSError(Exception):
    """Raised when text-to-speech synthesis fails."""


class TTSService(ABC):
    @abstractmethod
    def synthesize(self, text: str, output_path: str, *, language: str = "en") -> None:
        """Synthesize text to an audio file."""
