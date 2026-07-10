from app.modules.provider_adapter.base import StorageUploadRequest
from app.modules.storage.local_storage import LocalFileSystemStorage


async def test_local_storage_uploads_return_browser_loadable_urls(tmp_path):
    storage = LocalFileSystemStorage(str(tmp_path))
    request = StorageUploadRequest(
        file_bytes=b"fake-png",
        file_name="front.png",
        content_type="image/png",
        project_id="project-1",
    )

    generated = await storage.upload(request)
    canonical = await storage._upload_with_asset_id(
        request,
        "projects/project-1/characters/character-1/front.png",
    )

    assert generated.url.startswith("/local-storage/local-")
    assert generated.signed_url.startswith(f"{generated.url}?signature=local&expires=3600")
    assert canonical.url == "/local-storage/projects/project-1/characters/character-1/front.png"
    assert canonical.signed_url.startswith(f"{canonical.url}?signature=local&expires=3600")
    assert "file://" not in generated.url
    assert "file://" not in canonical.url
    assert (tmp_path / "projects/project-1/characters/character-1/front.png").read_bytes() == b"fake-png"
