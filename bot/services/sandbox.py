from pathlib import Path


class SandboxStorage:
    """Local temp storage for downloads/uploads."""

    def __init__(self, root: str = "/tmp/bot_files"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def list_files(self) -> list[str]:
        return [p.name for p in self.root.iterdir() if p.is_file()]

    def path_for(self, filename: str) -> Path:
        return self.root / filename

    def exists(self, filename: str) -> bool:
        return self.path_for(filename).is_file()

    def read_text(self, filename: str, limit: int = 4000) -> str:
        path = self.path_for(filename)
        if not path.is_file():
            raise FileNotFoundError(f"Local file nahi mili: {filename}")
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]

    def write_text(self, filename: str, content: str) -> Path:
        path = self.path_for(filename)
        path.write_text(content, encoding="utf-8")
        return path

    def write_bytes(self, filename: str, data: bytes) -> Path:
        path = self.path_for(filename)
        path.write_bytes(data)
        return path

    def delete(self, filename: str) -> None:
        path = self.path_for(filename)
        if not path.exists():
            raise FileNotFoundError(f"File nahi mili: {filename}")
        path.unlink()
