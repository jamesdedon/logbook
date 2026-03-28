import os
import time
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings


def _system_timezone() -> str:
    """Detect the system's local timezone name."""
    local_tz = time.tzname[0]
    # time.tzname gives abbreviations like 'CST'; try /etc/localtime via datetime
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
    # Fallback: read /etc/timezone or resolve /etc/localtime
    try:
        with open("/etc/timezone") as f:
            return f.read().strip()
    except FileNotFoundError:
        pass
    import os
    link = os.readlink("/etc/localtime")
    if "/zoneinfo/" in link:
        return link.split("/zoneinfo/", 1)[1]
    return "UTC"


class Settings(BaseSettings):
    db_path: str = "/data/logbook.db"
    host: str = "0.0.0.0"
    port: int = 8000
    timezone: str = _system_timezone()
    project_dir: str = os.path.join(os.path.expanduser("~"), "projects", "logbook")

    model_config = {"env_prefix": "LOGBOOK_"}

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"


settings = Settings()
