"""Thin intent helpers — list only when user clearly asks to list."""
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


SUBFOLDERS = ("insta", "picture", "pdf", "audio", "other", "tosspage", "map")


def _detect_media_kind(low: str) -> str:
    wants_video = bool(re.search(r"\b(video|videos|clip|clips|reel|reels)\b", low))
    wants_image = bool(re.search(
        r"\b(photo|photos|pic|pics|image|images|selfie|selfies|nude|nudes)\b",
        low,
    ))
    if wants_video and not wants_image:
        return "video"
    if wants_image and not wants_video:
        return "image"
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

    # Bare serial: "2"
    if re.fullmatch(r"\d{1,3}", low):
        return ParsedIntent(Intent.DRIVE_DOWNLOAD, serial=int(low))

    # Explicit download with number
    m = re.search(
        r"(?:download\s+(\d+)|(\d+)\s*(?:no\.?|number|num)?\s*(?:file)?\s*download|(\d+)\s*download)",
        low,
    )
    if m:
        serial = int(next(g for g in m.groups() if g))
        return ParsedIntent(
            Intent.DRIVE_DOWNLOAD,
            subfolder=_detect_subfolder(low),
            serial=serial,
        )

    # Natural send media request
    if re.search(
        r"\b(photo|photos|pic|pics|image|images|selfie|nudes?|video|videos|clip)s?\b",
        low,
    ) and re.search(
        r"\b(bhej|bhejo|bhejdo|bhej\s*do|send|dikha|dikhao|show|share|de\s*do|do)\b",
        low,
    ):
        return ParsedIntent(
            Intent.DRIVE_RANDOM,
            subfolder=_detect_subfolder(low),
            media_kind=_detect_media_kind(low),
        )

    if re.search(r"\b(photo|pic|pics|selfie|nude|nudes|video)\s*(bhej|bhejo|bhejdo|send)\b", low):
        return ParsedIntent(
            Intent.DRIVE_RANDOM,
            subfolder=_detect_subfolder(low),
            media_kind=_detect_media_kind(low),
        )

    # Random file
    if "random" in low or re.search(r"\bkoi\s*(bhi|bi)\b", low):
        if any(f in low for f in SUBFOLDERS) or "folder" in low or "map" in low or "drive" in low:
            return ParsedIntent(
                Intent.DRIVE_RANDOM,
                subfolder=_detect_subfolder(low),
                media_kind=_detect_media_kind(low),
            )

    # Search only if clearly search
    if low.startswith("/search") or low.startswith("search "):
        q = re.sub(r"^/?search\s*", "", raw, flags=re.I).strip()
        return ParsedIntent(Intent.DRIVE_SEARCH, search_query=q)

    # LIST only when user clearly wants a list
    list_markers = (
        "list", "lists", "folder list", "files list", "kya hai", "kya kya",
        "dikhao folder", "folder dikhao", "map dikhao", "folder dikha",
    )
    if any(m in low for m in list_markers) or re.search(
        r"\b(folder|map|drive)\b.*\b(dikha|dikhao|bata|batao|list)\b", low
    ) or re.search(r"\b(dikha|dikhao|bata|batao|list)\b.*\b(folder|map|drive|files)\b", low):
        return ParsedIntent(Intent.DRIVE_LIST, subfolder=_detect_subfolder(low))

    return ParsedIntent(Intent.CHAT)
