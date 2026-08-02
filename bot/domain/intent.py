"""Rule-based intent router — LLM se pehle."""
import re
from dataclasses import dataclass
from enum import Enum, auto


class Intent(Enum):
    DRIVE_LIST = auto()
    DRIVE_DOWNLOAD = auto()
    DRIVE_RANDOM = auto()
    DRIVE_SEARCH = auto()
    CHAT = auto()


@dataclass
class ParsedIntent:
    intent: Intent
    subfolder: str = "root"
    serial: int | None = None
    search_query: str = ""
    media_kind: str = "any"  # any | image | video


DRIVE_KEYWORDS = (
    "drive", "folder", "map", "list", "files",
    "insta", "picture", "pdf", "audio", "other", "tosspage",
    "download", "random",
)
SEND_MEDIA_RE = (
    r"\b(photo|photos|pic|pics|image|images|selfie|nudes?|video|videos|clip)s?\b"
)

SUBFOLDERS = ("insta", "picture", "pdf", "audio", "other", "tosspage", "map")



def _detect_media_kind(low: str) -> str:
    """User ne photo manga ya video — random filter ke liye."""
    wants_video = bool(re.search(r"\b(video|videos|clip|clips|reel|reels)\b", low))
    wants_image = bool(re.search(
        r"\b(photo|photos|pic|pics|image|images|selfie|selfies|nude|nudes|pic\b)\b",
        low,
    ))
    if wants_video and not wants_image:
        return "video"
    if wants_image and not wants_video:
        return "image"
    # "media bhej" / mixed → any
    return "any"

def _detect_subfolder(low: str) -> str:
    for folder in SUBFOLDERS:
        if folder in low:
            return folder
    return "root"


def parse_intent(text: str) -> ParsedIntent:
    raw = (text or "").strip()
    low = raw.lower()
    if not low:
        return ParsedIntent(Intent.CHAT)

    # Bare serial only: "2" / "12" → download (list pehle se hona chahiye)
    if re.fullmatch(r"\d{1,3}", low):
        return ParsedIntent(Intent.DRIVE_DOWNLOAD, serial=int(low))

    # Random: "insta se random" / "koi bhi file map se" / "random from picture"
    if "random" in low or re.search(r"\bkoi\s*(bhi|bi)\b", low):
        if any(k in low for k in DRIVE_KEYWORDS) or any(f in low for f in SUBFOLDERS):
            return ParsedIntent(Intent.DRIVE_RANDOM, subfolder=_detect_subfolder(low), media_kind=_detect_media_kind(low))

    # Natural "send me a photo/video" style requests → random media
    if re.search(
        r"\b(photo|photos|pic|pics|image|selfie|nudes?|video|clip)s?\b",
        low,
    ) and re.search(
        r"\b(bhej|bhejo|bhejdo|bhej\s*do|send|dikha|dikhao|show|share|do)\b",
        low,
    ):
        return ParsedIntent(Intent.DRIVE_RANDOM, subfolder=_detect_subfolder(low), media_kind=_detect_media_kind(low))

    # short forms: "photo bhej", "pic bhej do", "nude bhejo"
    if re.search(r"\b(photo|pic|pics|selfie|nude|nudes|video)\s*(bhej|bhejo|bhejdo|send)\b", low):
        return ParsedIntent(Intent.DRIVE_RANDOM, subfolder=_detect_subfolder(low), media_kind=_detect_media_kind(low))

    # Download with optional folder:
    # "insta folder se 2 no file download"
    # "2 download karo"
    # "download 3 from picture"
    m = re.search(
        r"(?:download\s+(\d+)|(\d+)\s*(?:no\.?|number|num)?\s*(?:file)?\s*download|(\d+)\s*download)",
        low,
    )
    if not m:
        m = re.search(r"(?:se|from)\s+(\d+)\s*(?:no|number|file)?", low)
    if m and ("download" in low or "file" in low or any(f in low for f in SUBFOLDERS)):
        serial = int(next(g for g in m.groups() if g))
        return ParsedIntent(
            Intent.DRIVE_DOWNLOAD,
            subfolder=_detect_subfolder(low),
            serial=serial,
        )
    # "2 download" already covered; plain "download 2"
    m2 = re.search(r"download\s+(\d+)", low)
    if m2:
        return ParsedIntent(
            Intent.DRIVE_DOWNLOAD,
            subfolder=_detect_subfolder(low),
            serial=int(m2.group(1)),
        )

    if low.startswith("/search") or low.startswith("search "):
        q = re.sub(r"^/?search\s*", "", raw, flags=re.I).strip()
        return ParsedIntent(Intent.DRIVE_SEARCH, search_query=q)

    if any(k in low for k in DRIVE_KEYWORDS):
        return ParsedIntent(Intent.DRIVE_LIST, subfolder=_detect_subfolder(low))

    return ParsedIntent(Intent.CHAT)
