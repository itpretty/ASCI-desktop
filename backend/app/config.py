import platform
from pathlib import Path


def get_data_dir() -> Path:
    """Get OS-appropriate app data directory."""
    system = platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    elif system == "Windows":
        base = Path(
            __import__("os").environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        )
    else:
        base = Path(
            __import__("os").environ.get(
                "XDG_DATA_HOME", Path.home() / ".local" / "share"
            )
        )
    data_dir = base / "ASCI-Desktop"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DATA_DIR = get_data_dir()
LANCEDB_DIR = DATA_DIR / "lancedb"
SQLITE_PATH = DATA_DIR / "asci.db"
