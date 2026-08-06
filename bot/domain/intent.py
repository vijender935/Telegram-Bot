"""Rule-based intent router — LLM se pehle."""
import re
from dataclasses import dataclass
from enum import Enum, auto


class Intent(Enum):
    DRIVE_LIST = auto()
    DRIVE_DOWNLOAD = auto()
    DRIVE_RANDOM = auto()
    DRIVE_SEARCH = auto()
    VOICE = auto()
    VAULT_ADD = auto()
    VAULT_LIST = auto()
    VAULT_OPEN = auto()
    CHAT = auto()


@dataclass
class ParsedIntent:
    intent: Intent
    subfolder: str = "root"
    serial: int | None = None
    search_query: str = ""
    media_kind: str = "any"  # any | image | video


SUBFOLDERS = ("insta", "picture", "pdf", "audio", "other", "tosspage", "map")

DRIVE_KEYWORDS = (
    "drive", "folder", "map", "list", "files",
    "insta", "picture", "pdf", "audio", "other", "tosspage",
    "download", "random",
)


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

    # Bare serial: "2" / "12"
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
    m2 = re.search(r"download\s+(\d+)", low)
    if m2:
        return ParsedIntent(
            Intent.DRIVE_DOWNLOAD,
            subfolder=_detect_subfolder(low),
            serial=int(m2.group(1)),
        )

    # Random: "insta se random" / "koi bhi file"
    if "random" in low or re.search(r"\bkoi\s*(bhi|bi)\b", low):
        if any(k in low for k in DRIVE_KEYWORDS) or any(f in low for f in SUBFOLDERS):
            return ParsedIntent(
                Intent.DRIVE_RANDOM,
                subfolder=_detect_subfolder(low),
                media_kind=_detect_media_kind(low),
            )

    # Natural "photo bhej" / "video bhej" / "pic dikhao"
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

    # Voice
    voice_markers = (
        "bol kar sunao", "bol ke sunao", "bol ke batao", "voice note",
        "audio bhej", "audio sunao", "suna do", "sunaao", "bol do",
    )
    if any(m in low for m in voice_markers) or re.search(
        r"\b(voice|audio|suna)\b.*\b(bhej|do|sunao)\b", low
    ):
        return ParsedIntent(Intent.VOICE)

    # Vault
    vault_markers = ("vault", "secret", "tijori", "khufiya", "khufia", "safe")
    if any(m in low for m in vault_markers):
        if any(x in low for x in ("dikha", "bata", "list", "kya hai", "kya kya")):
            return ParsedIntent(Intent.VAULT_LIST)
        if any(x in low for x in ("save", "daal", "rakh", "add", "store")):
            return ParsedIntent(Intent.VAULT_ADD)
        if any(x in low for x in ("khol", "open", "nikal")):
            return ParsedIntent(Intent.VAULT_OPEN)

    # Search
    if low.startswith("/search") or low.startswith("search "):
        q = re.sub(r"^/?search\s*", "", raw, flags=re.I).strip()
        return ParsedIntent(Intent.DRIVE_SEARCH, search_query=q)

    # List — only clear list asks
    list_markers = (
        "list", "lists", "folder list", "files list",
        "dikhao folder", "folder dikhao", "map dikhao", "folder dikha",
    )
    if any(m in low for m in list_markers) or re.search(
        r"\b(folder|map|drive)\b.*\b(dikha|dikhao|bata|batao|list)\b", low
    ) or re.search(
        r"\b(dikha|dikhao|bata|batao|list)\b.*\b(folder|map|drive|files)\b", low
    ):
        return ParsedIntent(Intent.DRIVE_LIST, subfolder=_detect_subfolder(low))

    return ParsedIntent(Intent.CHAT)
