import os
from pathlib import Path

# Magic-byte signatures -> file extension
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
]

_BASENAME = "background"

MAX_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB


def detect_extension(data: bytes) -> str | None:
    """Return 'png'/'jpg' based on magic bytes, or None if not a supported image."""
    for sig, ext in _SIGNATURES:
        if data.startswith(sig):
            return ext
    return None


def background_path(home: str) -> Path | None:
    """Return the path of the stored background image, or None if there isn't one."""
    for ext in ("png", "jpg"):
        path = Path(home) / f"{_BASENAME}.{ext}"
        if path.is_file():
            return path
    return None


def save_background(home: str, data: bytes) -> Path:
    """Validate and persist the background image, replacing any existing one.

    Raises ValueError if the data is not a PNG/JPEG or exceeds MAX_SIZE_BYTES.
    """
    if len(data) > MAX_SIZE_BYTES:
        raise ValueError(f"Image too large ({len(data)} bytes, max {MAX_SIZE_BYTES})")
    ext = detect_extension(data)
    if ext is None:
        raise ValueError("Unsupported image format (only PNG and JPEG are accepted)")

    home_dir = Path(home)
    home_dir.mkdir(parents=True, exist_ok=True)
    target = home_dir / f"{_BASENAME}.{ext}"

    # Write atomically, then remove any leftover file with the other extension
    tmp = target.with_suffix(f".{ext}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    for other in home_dir.glob(f"{_BASENAME}.*"):
        if other != target and other.suffix != ".tmp":
            other.unlink(missing_ok=True)
    return target


def delete_background(home: str) -> bool:
    """Remove the stored background image. Returns True if one existed."""
    path = background_path(home)
    if path is None:
        return False
    path.unlink(missing_ok=True)
    return True
