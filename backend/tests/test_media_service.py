import io
from pathlib import Path

import pytest
from PIL import Image

from app.core.errors import DomainValidationError
from app.services.media import MediaProcessor


def image_bytes(size: tuple[int, int] = (100, 80), image_format: str = "JPEG") -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", size, "red")
    image.save(output, format=image_format, exif=b"Exif\x00\x00test-metadata")
    return output.getvalue()


def test_media_processor_reencodes_into_public_directory(tmp_path: Path) -> None:
    result = MediaProcessor(tmp_path, 2_000_000, 1_000_000).process(
        image_bytes(), "photo.jpg", "portfolio_image"
    )

    detail = tmp_path / "public" / result.object_key
    thumb = tmp_path / "public" / result.thumbnail_object_key
    assert detail.exists()
    assert thumb.exists()
    assert not (tmp_path / result.object_key).exists()
    with Image.open(detail) as stored:
        assert stored.getexif() == {}
        assert stored.width <= 2400
    assert "photo.jpg" not in result.object_key


def test_media_processor_rejects_unsupported_content(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError):
        MediaProcessor(tmp_path, 2_000_000, 1_000_000).process(
            b"not-an-image", "payload.exe", "portfolio_image"
        )


def test_media_processor_rejects_pixel_bomb(tmp_path: Path) -> None:
    with pytest.raises(DomainValidationError):
        MediaProcessor(tmp_path, 2_000_000, 10_000).process(
            image_bytes((200, 200)), "large.jpg", "portfolio_image"
        )


def test_media_processor_deletes_from_public_directory(tmp_path: Path) -> None:
    processor = MediaProcessor(tmp_path, 2_000_000, 1_000_000)
    result = processor.process(image_bytes(), "photo.jpg", "portfolio_image")

    processor.delete(result.object_key)
    processor.delete(result.thumbnail_object_key)

    assert not (tmp_path / "public" / result.object_key).exists()
    assert not (tmp_path / "public" / result.thumbnail_object_key).exists()
