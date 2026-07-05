import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

from pydantic import BaseModel

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"

# 单期/单集内容
class GalleryEpisode(BaseModel):
    title: str              # 标题
    description: str        # 描述
    audio_url: str          # 音频 URL（导入时的下载地址）
    pub_date: str           # 发布日期
    duration: str | None    # 时长
    program: str            # 节目名称
    program_id: str         # 节目 ID
    level: str              # 难度
    source: str             # 来源
    source_label: str       # 来源标签

# 内容提供者
class ContentProvider(ABC):
    source: str             # 来源
    source_label: str       # 来源标签

    @abstractmethod
    async def fetch(self) -> list[GalleryEpisode]: ...


def parse_duration(raw: str | None) -> str | None:
    """Normalize itunes:duration to mm:ss or hh:mm:ss."""
    if not raw:
        return None
    raw = raw.strip()
    if ":" in raw:
        return raw
    try:
        secs = int(raw)
        mins, s = divmod(secs, 60)
        h, m = divmod(mins, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except ValueError:
        return raw


def parse_pub_date(raw: str | None) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return raw


def parse_feed(xml_text: str, program: dict, source: str, source_label: str) -> list[GalleryEpisode]:
    """Parse a standard RSS feed into GalleryEpisode list."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    channel = root.find("channel")
    if channel is None:
        return []

    episodes: list[GalleryEpisode] = []
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        if enclosure is None:
            continue
        audio_url = enclosure.get("url", "")
        enc_type = enclosure.get("type", "")
        if not audio_url:
            continue
        if not (enc_type.startswith("audio/") or enc_type.startswith("video/")
                or audio_url.lower().endswith((".mp3", ".mp4"))):
            continue

        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else "Untitled"

        desc_el = item.find("description")
        description = ""
        if desc_el is not None and desc_el.text:
            description = re.sub(r"<[^>]+>", "", desc_el.text).strip()

        pub_date_el = item.find("pubDate")
        pub_date = parse_pub_date(pub_date_el.text if pub_date_el is not None else None)

        duration_el = item.find(f"{{{ITUNES_NS}}}duration")
        duration = parse_duration(duration_el.text if duration_el is not None else None)

        episodes.append(GalleryEpisode(
            title=title,
            description=description,
            audio_url=audio_url,
            pub_date=pub_date,
            duration=duration,
            program=program["name"],
            program_id=program["id"],
            level=program["level"],
            source=source,
            source_label=source_label,
        ))

    return episodes
