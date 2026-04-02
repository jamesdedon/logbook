import os
import platform
import time
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings


def _system_timezone() -> str:
    """Detect the system's local timezone name."""
    if platform.system() == "Darwin":
        # macOS: read /etc/localtime symlink
        try:
            link = os.readlink("/etc/localtime")
            if "/zoneinfo/" in link:
                return link.split("/zoneinfo/", 1)[1]
        except OSError:
            pass
    else:
        # Linux: try timedatectl first, then /etc/timezone, then /etc/localtime
        try:
            import subprocess
            result = subprocess.run(
                ["timedatectl", "show", "--property=Timezone", "--value"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        try:
            with open("/etc/timezone") as f:
                return f.read().strip()
        except FileNotFoundError:
            pass
        try:
            link = os.readlink("/etc/localtime")
            if "/zoneinfo/" in link:
                return link.split("/zoneinfo/", 1)[1]
        except OSError:
            pass
    return "UTC"


_DEFAULT_HOME = os.environ.get(
    "LOGBOOK_HOME",
    os.path.join(os.path.expanduser("~"), ".logbook"),
)


class Settings(BaseSettings):
    home: str = _DEFAULT_HOME
    db_path: str = os.path.join(_DEFAULT_HOME, "logbook.db")
    host: str = "0.0.0.0"
    port: int = 8000
    timezone: str = _system_timezone()
    project_dir: str = _DEFAULT_HOME
    backup_path: str = "/mnt/nas-james/logbook"

    model_config = {
        "env_prefix": "LOGBOOK_",
        "env_file": os.path.join(_DEFAULT_HOME, ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


settings = Settings()
