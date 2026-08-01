"""Rule-based intent router — LLM se pehle."""
import re
from dataclasses import dataclass
from enum import Enum, auto


class Intent(Enum):
    DRIVE_LIST = auto()
    DRIVE_DOWNLOAD = auto()
    DRIVE_SEARCH = auto()
    CHAT = auto()


@dataclass
class ParsedIntent:
    intent: Intent
    subfolder: str = "root"
    serial: int | None = None
    search_query: str = ""


DRIVE_KEYWORDS = (
    "drive", "folder", "map", "list", "files",
    "insta", "picture", "pdf", "audio", "other", "tosspage",
)
SUBFOLDERS = ("insta", "picture", "pdf", "audio", "other", "tosspage")


def parse_intent(text: str) -> ParsedIntent:
    low = (text or "").lower().strip()
    if not low:
        return ParsedIntent(Intent.CHAT)

    m = re.search(r"(?:download\s+(\d+)|(\d+)\s*download)", low)
    if m:
        return ParsedIntent(Intent.DRIVE_DOWNLOAD, serial=int(m.group(1) or m.group(2)))

    if low.startswith("/search") or low.startswith("search "):
        q = re.sub(r"^/?search\s*", "", text, flags=re.I).strip()
        return ParsedIntent(Intent.DRIVE_SEARCH, search_query=q)

    if any(k in low for k in DRIVE_KEYWORDS):
        sub = "root"
        for folder in SUBFOLDERS:
            if folder in low:
                sub = folder
                break
        if "map" in low and sub == "root":
            sub = "map"
        return ParsedIntent(Intent.DRIVE_LIST, subfolder=sub)

    return ParsedIntent(Intent.CHAT)
