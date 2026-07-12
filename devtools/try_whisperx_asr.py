"""WhisperX 语音识别 + 强制对齐试用脚本（独立运行，不依赖项目代码）。

依赖：pip install whisperx

示例：
  python try_whisperx_asr.py echoic_test_files/test_mp3.mp3
  python try_whisperx_asr.py echoic_test_files/test_mp3.mp3 --document echoic_test_files/test_txt.txt
  python try_whisperx_asr.py echoic_test_files/test_mp3.mp3 --document echoic_test_files/test_txt.txt --use-asr-timing
"""

from __future__ import annotations

import argparse
from pathlib import Path
from pprint import pprint

import nltk
import whisperx
from nltk.tokenize import sent_tokenize
from whisperx.utils import PUNKT_LANGUAGES

DEFAULT_MAX_WORDS = 32
_LANGUAGES_WITHOUT_SPACES = {"ja", "zh"}


def _load_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"参考文档为空: {path}")
    return text


def _split_units(text: str, max_words: int, language: str = "en") -> list[str]:
    """按行拆分后 NLTK Punkt 分句，超长句按 max_words 切块。"""
    lines = [" ".join(part.split()) for part in text.strip().splitlines() if part.strip()]
    normalized = " ".join(lines)
    if language in _LANGUAGES_WITHOUT_SPACES:
        sentences = lines or [normalized]
    else:
        punkt_lang = PUNKT_LANGUAGES.get(language, "english")
        sentences: list[str] = []
        for line in lines:
            try:
                sentences.extend(sent_tokenize(line, language=punkt_lang))
            except LookupError:
                nltk.download("punkt_tab", quiet=True)
                sentences.extend(sent_tokenize(line, language=punkt_lang))

    units: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        for i in range(0, len(words), max_words):
            units.append(" ".join(words[i : i + max_words]))
    return units or [normalized]


def _assign_timing(units: list[str], start: float, end: float) -> list[dict]:
    """按词数比例分配 [start, end] 时间窗。"""
    weights = [max(len(unit.split()), 1) for unit in units]
    total = sum(weights)
    cursor = start
    segments: list[dict] = []
    for unit, weight in zip(units, weights):
        duration = (end - start) * weight / total
        segments.append({"start": cursor, "end": cursor + duration, "text": unit})
        cursor += duration
    return segments


def _align(audio, segments: list[dict], language: str, device: str) -> dict:
    align_model, align_metadata = whisperx.load_align_model(
        language_code=language,
        device=device,
    )
    return whisperx.align(
        segments,
        align_model,
        align_metadata,
        audio,
        device,
        return_char_alignments=False,
    )


def _forced_align(
    audio_file: str,
    reference_text: str,
    *,
    language: str,
    device: str,
    max_words: int,
    use_asr_timing: bool,
    model_size: str,
    compute_type: str,
    batch_size: int,
) -> None:
    audio = whisperx.load_audio(audio_file)
    duration = len(audio) / 16000.0
    units = _split_units(reference_text, max_words, language)

    if use_asr_timing:
        asr_model = whisperx.load_model(model_size, device, compute_type=compute_type)
        asr = asr_model.transcribe(audio, batch_size=batch_size, language=language)
        asr_segments = asr["segments"]
        if asr_segments:
            start = float(asr_segments[0]["start"])
            end = float(asr_segments[-1]["end"])
            print("=== ASR 时间边界 (segments) ===")
            pprint(asr_segments)
        else:
            start, end = 0.0, duration
            print("=== ASR 无结果，回退到整段音频 ===")
    else:
        start, end = 0.0, duration

    segments = _assign_timing(units, start, end)
    result = _align(audio, segments, language, device)
    print("=== 强制对齐结果 (segments) ===")
    pprint(result.get("segments", []))


def _transcribe_and_align(
    audio_file: str,
    *,
    model_size: str,
    device: str,
    compute_type: str,
    batch_size: int,
    language: str | None,
) -> None:
    audio = whisperx.load_audio(audio_file)
    asr_model = whisperx.load_model(model_size, device, compute_type=compute_type)
    kwargs: dict = {"batch_size": batch_size}
    if language:
        kwargs["language"] = language
    asr = asr_model.transcribe(audio, **kwargs)

    print("=== ASR 结果 (segments) ===")
    pprint(asr["segments"])

    result = _align(audio, asr["segments"], asr["language"], device)
    print("=== 词级对齐结果 (segments) ===")
    pprint(result["segments"])


def main() -> None:
    parser = argparse.ArgumentParser(description="WhisperX 语音识别 + 强制对齐")
    parser.add_argument("audio", help="音频文件路径")
    parser.add_argument("-d", "--document", type=Path, help="参考文本；提供时做强制对齐")
    parser.add_argument("-l", "--language", default="en", help="语言代码（默认 en）")
    parser.add_argument("--model-size", default="small")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--compute-type", default="float32")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-words", type=int, default=DEFAULT_MAX_WORDS)
    parser.add_argument(
        "--use-asr-timing",
        action="store_true",
        help="强制对齐时用 ASR 首尾时间作为语音区间（需配合 --document）",
    )
    args = parser.parse_args()

    if args.document:
        _forced_align(
            args.audio,
            _load_text(args.document),
            language=args.language,
            device=args.device,
            max_words=max(1, args.max_words),
            use_asr_timing=args.use_asr_timing,
            model_size=args.model_size,
            compute_type=args.compute_type,
            batch_size=args.batch_size,
        )
    else:
        _transcribe_and_align(
            args.audio,
            model_size=args.model_size,
            device=args.device,
            compute_type=args.compute_type,
            batch_size=args.batch_size,
            language=args.language or None,
        )


if __name__ == "__main__":
    main()
