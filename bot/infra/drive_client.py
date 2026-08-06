import io
import json
import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from bot.infra.serial_map import FileEntry, SerialMapStore

logger = logging.getLogger(__name__)


class DriveClient:
    """Google Drive access limited to configured root folder + subfolders."""

    MIME_LABELS = {
        "application/vnd.google-apps.folder": "📁 Folder",
        "application/vnd.google-apps.document": "📝 Doc",
        "application/vnd.google-apps.spreadsheet": "📊 Sheet",
        "application/pdf": "📄 PDF",
        "image/jpeg": "🖼️ JPEG",
        "image/png": "🖼️ PNG",
        "video/mp4": "🎬 MP4",
        "video/quicktime": "🎬 MOV",
        "audio/mpeg": "🎵 MP3",
        "audio/ogg": "🎵 OGG",
        "text/plain": "📃 Text",
    }

    def __init__(self, folder_id: str, sa_json: str, serial_store: SerialMapStore):
        if not folder_id or not sa_json:
            raise ValueError("Drive credentials missing")
        self.folder_id = folder_id
        self.serial_store = serial_store
        self._folder_cache: dict[str, str] = {}
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        self._service = build("drive", "v3", credentials=creds)

    def mime_label(self, mime: str) -> str:
        if mime in self.MIME_LABELS:
            return self.MIME_LABELS[mime]
        if mime.startswith("video/"):
            return "🎬 Video"
        if mime.startswith("image/"):
            return "🖼️ Image"
        if mime.startswith("audio/"):
            return "🎵 Audio"
        return f"📎 {mime.split('/')[-1] if mime else 'File'}"

    def find_folder_id(self, name: str, parent_id: str | None = None) -> str | None:
        key = name.lower().strip()
        if key in self._folder_cache:
            return self._folder_cache[key]
        root = parent_id or self.folder_id
        q = (
            f"'{root}' in parents and "
            f"mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        res = self._service.files().list(
            q=q, pageSize=50, fields="files(id,name)",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        folders = res.get("files", [])
        for f in folders:
            if f["name"].lower().strip() == key:
                self._folder_cache[key] = f["id"]
                return f["id"]
        for sub in folders:
            found = self.find_folder_id(name, parent_id=sub["id"])
            if found:
                return found
        return None

    def list_files(self, user_id: int, subfolder_name: str = "root") -> str:
        target_id = self.folder_id
        label = "Map"
        name = (subfolder_name or "root").strip()
        low = name.lower()

        if low not in ("", "root", "main", "map"):
            found = self.find_folder_id(name)
            if not found:
                q = (
                    f"'{self.folder_id}' in parents and "
                    f"mimeType='application/vnd.google-apps.folder' and trashed=false"
                )
                res = self._service.files().list(
                    q=q, pageSize=30, fields="files(name)",
                    supportsAllDrives=True, includeItemsFromAllDrives=True,
                ).execute()
                available = [f["name"] for f in res.get("files", [])]
                msg = f"Subfolder nahi mili: '{name}'"
                if available:
                    msg += "\n\nMap ke andar:\n• " + "\n• ".join(available)
                return msg
            target_id = found
            label = name

        res = self._service.files().list(
            q=f"'{target_id}' in parents and trashed=false",
            pageSize=100,
            fields="files(id,name,mimeType,size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            orderBy="folder,name",
        ).execute()

        files = res.get("files", [])
        if not files:
            self.serial_store.set_list(user_id, {})
            return f"'{label}' folder khali hai."

        entries: dict[int, FileEntry] = {}
        lines = [f"📁 {label}\n"]
        for i, f in enumerate(files, start=1):
            entries[i] = FileEntry(
                file_id=f["id"], name=f["name"], mime=f.get("mimeType", "")
            )
            tag = self.mime_label(f.get("mimeType", ""))
            size = f.get("size")
            if size:
                n = int(size)
                sz = f"{n // (1024*1024)} MB" if n > 1024 * 1024 else f"{max(1, n // 1024)} KB"
                lines.append(f"{i}. {f['name']}  [{tag}]  {sz}")
            else:
                lines.append(f"{i}. {f['name']}  [{tag}]")

        self.serial_store.set_list(user_id, entries)
        lines.append("\nNumber bhej dena agar koi file chahiye.")
        return "\n".join(lines)

    def download_to_path(self, file_id: str, dest: Path, mime: str = "") -> None:
        if not mime:
            meta = self._service.files().get(fileId=file_id, fields="mimeType").execute()
            mime = meta.get("mimeType", "")

        if mime.startswith("application/vnd.google-apps."):
            export = "text/plain"
            if "spreadsheet" in mime:
                export = "text/csv"
            elif "presentation" in mime:
                export = "application/pdf"
            data = self._service.files().export(fileId=file_id, mimeType=export).execute()
            raw = data if isinstance(data, bytes) else data.encode("utf-8")
            dest.write_bytes(raw)
        else:
            req = self._service.files().get_media(fileId=file_id)
            with open(dest, "wb") as fh:
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()


    def _resolve_folder(self, subfolder_name: str) -> tuple[str, str]:
        """Return (folder_id, label)."""
        name = (subfolder_name or "root").strip()
        low = name.lower()
        if low in ("", "root", "main", "map"):
            return self.folder_id, "Map"
        found = self.find_folder_id(name)
        if not found:
            raise FileNotFoundError(name)
        return found, name

    def _list_entries(self, target_id: str) -> dict[int, FileEntry]:
        res = self._service.files().list(
            q=f"'{target_id}' in parents and trashed=false",
            pageSize=100,
            fields="files(id,name,mimeType,size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            orderBy="folder,name",
        ).execute()
        files = res.get("files", [])
        entries: dict[int, FileEntry] = {}
        for i, f in enumerate(files, start=1):
            entries[i] = FileEntry(
                file_id=f["id"], name=f["name"], mime=f.get("mimeType", "")
            )
        return entries

    def download_by_serial(
        self, user_id: int, serial: int, dest_dir: Path, subfolder: str = "root"
    ) -> tuple[str, str]:
        """One-shot: optional subfolder list → serial download. List cache update."""
        entry = self.serial_store.get(user_id, serial)

        # Agar list miss / expire aur subfolder diya → pehle list banao silently
        if not entry and subfolder:
            try:
                target_id, _ = self._resolve_folder(subfolder)
            except FileNotFoundError:
                return "error", f"Folder nahi mili: {subfolder}"
            entries = self._list_entries(target_id)
            if not entries:
                return "error", f"'{subfolder}' khali hai."
            self.serial_store.set_list(user_id, entries)
            entry = entries.get(int(serial))

        if not entry:
            entry = self.serial_store.get(user_id, serial)
        if not entry:
            return "error", "Serial invalid ya list expire. Pehle list karo YA: insta se 2 download karo"

        dest = dest_dir / Path(entry.name).name
        try:
            self.download_to_path(entry.file_id, dest, entry.mime)
            return "ok", dest.name
        except Exception as e:
            logger.exception("download failed")
            return "error", f"Download fail: {type(e).__name__}: {e}"


    def download_random(
        self, user_id: int, subfolder: str, dest_dir: Path, media_kind: str = "any"
    ) -> tuple[str, str]:
        """Random file. media_kind: any | image | video"""
        import random
        try:
            target_id, label = self._resolve_folder(subfolder)
        except FileNotFoundError:
            return "error", f"Folder nahi mili: {subfolder}"
        entries = self._list_entries(target_id)
        kind = (media_kind or "any").lower()
        img_ext = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic")
        vid_ext = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")

        def match(entry) -> bool:
            if entry.mime == "application/vnd.google-apps.folder":
                return False
            ext = Path(entry.name).suffix.lower()
            if kind == "image":
                return entry.mime.startswith("image/") or ext in img_ext
            if kind == "video":
                return entry.mime.startswith("video/") or ext in vid_ext
            return True

        files = {k: v for k, v in entries.items() if match(v)}
        if not files:
            want = {"image": "photo/image", "video": "video"}.get(kind, "downloadable")
            return "error", f"'{label}' mein koi {want} file nahi mili."
        self.serial_store.set_list(user_id, entries)
        serial = random.choice(list(files.keys()))
        entry = files[serial]
        dest = dest_dir / Path(entry.name).name
        try:
            self.download_to_path(entry.file_id, dest, entry.mime)
            return "ok", dest.name
        except Exception as e:
            logger.exception("random download failed")
            return "error", f"Fail: {e}"



    def search(self, query: str) -> str:
        if not query.strip():
            return "Search query empty."
        # Use semantic search keywords
        q = f"name contains '{query.strip()}' and trashed=false"
        res = self._service.files().list(
            q=q,
            pageSize=30,
            fields="files(name,mimeType)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        if not files:
            return f"Koi file nahi mili: '{query}'"
        lines = [f"🔍 {query}\n"]
        for f in files:
            lines.append(f"• {f['name']}  [{self.mime_label(f.get('mimeType', ''))}]")
        return "\n".join(lines)

    def semantic_download(self, user_id: int, description: str, dest_dir: Path) -> tuple[str, str]:
        """Search for a file matching description and download it."""
        import random
        q = f"name contains '{description.strip()}' and trashed=false"
        try:
            res = self._service.files().list(
                q=q, pageSize=10, fields="files(id,name,mimeType)",
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            files = res.get("files", [])
            if not files:
                # Fallback to random if search fails
                return self.download_random(user_id, "root", dest_dir)
            
            entry = random.choice(files)
            dest = dest_dir / Path(entry['name']).name
            self.download_to_path(entry['id'], dest, entry['mimeType'])
            return "ok", dest.name
        except Exception as e:
            logger.exception("semantic download failed")
            return "error", str(e)

    def upload(self, local_path: Path, drive_name: str | None = None) -> str:
        name = drive_name or local_path.name
        meta = {"name": name, "parents": [self.folder_id]}
        media = MediaFileUpload(str(local_path), resumable=True)
        uploaded = self._service.files().create(
            body=meta, media_body=media, fields="id,name", supportsAllDrives=True
        ).execute()
        return uploaded.get("name", name)
