import subprocess
from pathlib import Path

from app.config import LocalMediaConfig
from app.services.media.base import MediaError, MediaService

_VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".flv", ".wmv"}
_PDF_SUFFIXES = {".pdf"}
_TXT_SUFFIXES = {".txt"}
_MD_SUFFIXES = {".md"}
_HTML_SUFFIXES = {".html", ".htm"}
_DOCX_SUFFIXES = {".docx"}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
# Tesseract language codes — keys match ASR__WHISPERX__LANGUAGE
_TESSERACT_LANGS = {"en": "eng", "fr": "fra", "de": "deu", "ja": "jpn"}
_OCR_DPI = 200
# Markdown → HTML extensions（可按需扩展，如 "toc", "meta"）
_MARKDOWN_EXTENSIONS = ["extra", "sane_lists"]
_MARKDOWN_BLOCK_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "blockquote", "pre", "td", "th"}
_STRIP_TAGS = ["script", "style", "noscript"]


def _subprocess_media_error(tool: str, exc: subprocess.CalledProcessError) -> MediaError:
    stderr = (exc.stderr or b"").decode(errors="replace").strip()
    detail = stderr.splitlines()[-1] if stderr else str(exc)
    if tool == "ffmpeg" and "does not contain any stream" in stderr.lower():
        return MediaError("Video contains no audio track")
    return MediaError(f"{tool} failed: {detail}")


class LocalMediaService(MediaService):
    """Local media conversion using ffmpeg, pymupdf, python-docx, and tesseract OCR."""

    def __init__(self, config: LocalMediaConfig):
        self.config = config

    def media_kind(self, filename: str, content_type: str | None = None) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix in _PDF_SUFFIXES or (content_type and "pdf" in content_type):
            return "pdf"
        if suffix in _DOCX_SUFFIXES or (content_type and "wordprocessingml" in content_type):
            return "docx"
        if suffix in _MD_SUFFIXES or content_type == "text/markdown":
            return "md"
        if suffix in _HTML_SUFFIXES or content_type == "text/html":
            return "html"
        if suffix in _TXT_SUFFIXES or content_type == "text/plain":
            return "text"
        if suffix in _IMAGE_SUFFIXES or (content_type and content_type.startswith("image/")):
            return "image"
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

    def extract_text(self, src_path: str, *, kind: str, language: str = "en") -> str:
        if kind == "pdf":
            return self._extract_pdf_text(src_path, language=language)
        if kind == "text":
            return self._extract_plain_text(src_path)
        if kind == "md":
            return self._extract_markdown_text(src_path)
        if kind == "html":
            return self._extract_html_text(src_path)
        if kind == "docx":
            return self._extract_docx_text(src_path)
        if kind == "image":
            return self._extract_image_text(src_path, language=language)
        raise MediaError(f"extract_text not supported for {kind!r}")

    def _ocr_image(self, img, *, language: str) -> str:
        import pytesseract

        lang = _TESSERACT_LANGS.get(language, language)
        try:
            return pytesseract.image_to_string(img, lang=lang).strip()
        except pytesseract.TesseractNotFoundError as e:
            raise MediaError("tesseract not found") from e
        except Exception as e:
            raise MediaError(f"OCR failed: {e}") from e

    def _read_text_file(self, src_path: str) -> str:
        path = Path(src_path)
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise MediaError("Failed to read text file: unsupported encoding")

    def _soup_to_plain(self, soup) -> str:
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        blocks: list[str] = []
        for tag in soup.find_all(_MARKDOWN_BLOCK_TAGS):
            if tag.find_parent(_MARKDOWN_BLOCK_TAGS):
                continue
            block = tag.get_text(" ", strip=True)
            if block:
                blocks.append(block)
        plain = "\n".join(blocks) if blocks else soup.get_text("\n", strip=True)
        while "\n\n\n" in plain:
            plain = plain.replace("\n\n\n", "\n\n")
        return plain.strip()

    def _markdown_to_plain(self, text: str) -> str:
        import markdown
        from bs4 import BeautifulSoup

        try:
            html = markdown.markdown(text, extensions=_MARKDOWN_EXTENSIONS)
        except Exception as e:
            raise MediaError(f"Failed to parse Markdown: {e}") from e
        return self._soup_to_plain(BeautifulSoup(html, "html.parser"))

    def _html_to_plain(self, text: str) -> str:
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(text, "html.parser")
        except Exception as e:
            raise MediaError(f"Failed to parse HTML: {e}") from e
        return self._soup_to_plain(soup)

    def _extract_plain_text(self, src_path: str) -> str:
        text = self._read_text_file(src_path).strip()
        if not text:
            raise MediaError("File contains no text")
        return text

    def _extract_markdown_text(self, src_path: str) -> str:
        text = self._markdown_to_plain(self._read_text_file(src_path))
        if not text:
            raise MediaError("Markdown file contains no extractable text")
        return text

    def _extract_html_text(self, src_path: str) -> str:
        text = self._html_to_plain(self._read_text_file(src_path))
        if not text:
            raise MediaError("HTML file contains no extractable text")
        return text

    def _extract_docx_text(self, src_path: str) -> str:
        from docx import Document

        try:
            doc = Document(src_path)
        except Exception as e:
            raise MediaError(f"Failed to read DOCX: {e}") from e
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
        if not text:
            raise MediaError("DOCX contains no extractable text")
        return text

    def _extract_image_text(self, src_path: str, *, language: str = "en") -> str:
        from PIL import Image

        try:
            img = Image.open(src_path)
        except Exception as e:
            raise MediaError(f"Failed to read image: {e}") from e
        text = self._ocr_image(img, language=language)
        if not text:
            raise MediaError("Image contains no extractable text")
        return text

    def _extract_pdf_text(self, src_path: str, *, language: str = "en") -> str:
        import io

        import fitz  # 项目名字：PyMuPDF，导入包名：fitz
        from PIL import Image

        try:
            doc = fitz.open(src_path)
        except Exception as e:
            raise MediaError(f"Failed to read PDF: {e}") from e
        try:
            text = "\n".join(page.get_text() for page in doc).strip()
            if text:
                return text
            # Scanned PDF: no embedded text — fall back to OCR
            parts: list[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=_OCR_DPI)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                parts.append(self._ocr_image(img, language=language))
            text = "\n".join(parts).strip()
            if not text:
                raise MediaError("PDF contains no extractable text")
            return text
        finally:
            doc.close()

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
