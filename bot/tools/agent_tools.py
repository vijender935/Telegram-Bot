from langchain_core.tools import tool


def build_tools(drive, sandbox) -> list:
    @tool
    def list_drive_files(subfolder_name: str = "root") -> str:
        """Map ya subfolder (Insta, Picture, PDF, Audio…) ki files list — serial numbers ke saath."""
        try:
            return drive.list_files(subfolder_name)
        except Exception as e:
            return f"Drive list error: {e}"

    @tool
    def download_by_serial(serial: int) -> str:
        """Last list se serial number se file download. Pehle list_drive_files chalao."""
        try:
            status, msg = drive.download_by_serial(int(serial), sandbox)
            if status == "ok":
                return f"DOWNLOAD_READY::{msg}"
            return msg
        except Exception as e:
            return f"Download error: {e}"

    @tool
    def search_drive_files(query: str) -> str:
        """Drive mein file naam se search."""
        try:
            return drive.search(query)
        except Exception as e:
            return f"Search error: {e}"

    @tool
    def list_local_files() -> str:
        """Local sandbox files."""
        files = sandbox.list_files()
        return "\n".join(files) if files else "Sandbox khali hai."

    @tool
    def upload_to_drive(local_filename: str, drive_filename: str = "") -> str:
        """Sandbox se Map folder mein upload."""
        try:
            path = sandbox.path_for(local_filename)
            if not path.exists():
                return f"Local file nahi mili: {local_filename}"
            name = drive.upload(path, drive_filename or None)
            return f"Upload successful → {name}"
        except Exception as e:
            return f"Upload error: {e}"

    return [
        list_drive_files,
        download_by_serial,
        search_drive_files,
        list_local_files,
        upload_to_drive,
    ]
