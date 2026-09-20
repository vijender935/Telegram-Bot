from pathlib import Path


class SandboxStorage:
    def __init__(self, root: str = "/tmp/bot_files"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, filename: str) -> Path:
        # prevent path traversal
        name = Path(filename).name
        return self.root / name

    def exists(self, filename: str) -> bool:
        return self.path_for(filename).is_file()

    def list_files(self) -> list[str]:
        return [p.name for p in self.root.iterdir() if p.is_file()]

    def write_bytes(self, filename: str, data: bytes) -> Path:
        path = self.path_for(filename)
        path.write_bytes(data)
        return path

    def delete(self, filename: str) -> None:
        path = self.path_for(filename)
        if path.exists():
            path.unlink()
