import pytest
from httpx import AsyncClient

from logbook.config import settings

# Minimal valid image payloads (magic bytes + filler)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture
def bg_home(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "home", str(tmp_path))
    return tmp_path


async def test_get_background_when_none_set(client: AsyncClient, bg_home):
    resp = await client.get("/background")
    assert resp.status_code == 404


async def test_put_and_get_png(client: AsyncClient, bg_home):
    resp = await client.put(
        "/background", content=PNG_BYTES, headers={"Content-Type": "image/png"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {"saved": True, "content_type": "image/png"}
    assert (bg_home / "background.png").read_bytes() == PNG_BYTES

    resp = await client.get("/background")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == PNG_BYTES


async def test_put_and_get_jpeg(client: AsyncClient, bg_home):
    resp = await client.put(
        "/background", content=JPEG_BYTES, headers={"Content-Type": "image/jpeg"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["content_type"] == "image/jpeg"

    resp = await client.get("/background")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == JPEG_BYTES


async def test_put_replaces_existing(client: AsyncClient, bg_home):
    await client.put("/background", content=PNG_BYTES)
    await client.put("/background", content=JPEG_BYTES)

    # Only the new file remains
    assert not (bg_home / "background.png").exists()
    assert (bg_home / "background.jpg").exists()

    resp = await client.get("/background")
    assert resp.headers["content-type"] == "image/jpeg"
    assert resp.content == JPEG_BYTES


async def test_put_rejects_non_image(client: AsyncClient, bg_home):
    resp = await client.put("/background", content=b"<html>not an image</html>")
    assert resp.status_code == 415
    # Nothing was written
    assert list(bg_home.iterdir()) == []


async def test_put_rejects_empty_body(client: AsyncClient, bg_home):
    resp = await client.put("/background", content=b"")
    assert resp.status_code == 400


async def test_put_rejects_oversized_image(client: AsyncClient, bg_home, monkeypatch):
    from logbook.services import background as svc

    monkeypatch.setattr(svc, "MAX_SIZE_BYTES", 16)
    resp = await client.put("/background", content=PNG_BYTES)
    assert resp.status_code == 415
    assert "too large" in resp.json()["detail"].lower()


async def test_delete_background(client: AsyncClient, bg_home):
    await client.put("/background", content=PNG_BYTES)

    resp = await client.delete("/background")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"deleted": True}
    assert not (bg_home / "background.png").exists()

    resp = await client.get("/background")
    assert resp.status_code == 404

    # Deleting again reports nothing to delete
    resp = await client.delete("/background")
    assert resp.json()["data"] == {"deleted": False}
