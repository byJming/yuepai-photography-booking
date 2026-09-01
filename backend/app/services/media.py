from __future__ import annotations

import hashlib
import io
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import DomainValidationError

_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class ProcessedMedia:
    object_key: str
    thumbnail_object_key: str
    mime_type: str
    file_size: int
    width: int
    height: int
    sha256: str


class MediaProcessor:
    """在受控目录内重编码图片，移除 EXIF 并生成展示图与缩略图。"""

    def __init__(self, root: Path, max_upload_bytes: int, max_pixels: int) -> None:
        self._root = root.resolve()
        self._public_root = (self._root / "public").resolve()
        if self._root not in self._public_root.parents:
            raise ValueError("媒体公开目录必须位于媒体根目录内。")
        self._max_upload_bytes = max_upload_bytes
        self._max_pixels = max_pixels

    def _public_path(self, object_key: str) -> Path:
        path = (self._public_root / object_key).resolve()
        if self._public_root not in path.parents:
            raise DomainValidationError("媒体存储路径无效。")
        return path

    @staticmethod
    def _flatten(image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")

    @staticmethod
    def _fit(image: Image.Image, longest_edge: int) -> Image.Image:
        result = image.copy()
        result.thumbnail((longest_edge, longest_edge), Image.Resampling.LANCZOS)
        return result

    def process(self, content: bytes, original_name: str, kind: str) -> ProcessedMedia:
        del original_name
        if not content or len(content) > self._max_upload_bytes:
            raise DomainValidationError("图片为空或超过上传大小限制。")
        try:
            with Image.open(io.BytesIO(content)) as opened:
                if opened.format not in _ALLOWED_FORMATS:
                    raise DomainValidationError("仅支持 JPEG、PNG 和 WebP 图片。")
                if opened.width * opened.height > self._max_pixels:
                    raise DomainValidationError("图片像素尺寸超过限制。")
                opened.load()
                source = self._flatten(ImageOps.exif_transpose(opened))
        except DomainValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise DomainValidationError("无法识别该图片，请更换文件。") from exc

        now = datetime.now(UTC)
        folder = Path(kind) / f"{now:%Y}" / f"{now:%m}"
        random_name = secrets.token_hex(16)
        object_key = (folder / f"{random_name}.jpg").as_posix()
        thumbnail_key = (folder / f"{random_name}-thumb.jpg").as_posix()
        detail_path = self._public_path(object_key)
        thumbnail_path = self._public_path(thumbnail_key)
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_tmp = detail_path.with_suffix(".tmp")
        thumbnail_tmp = thumbnail_path.with_suffix(".tmp")
        try:
            detail = self._fit(source, 2400)
            thumbnail = self._fit(source, 600)
            detail.save(detail_tmp, format="JPEG", quality=88, optimize=True, progressive=True)
            thumbnail.save(
                thumbnail_tmp,
                format="JPEG",
                quality=82,
                optimize=True,
                progressive=True,
            )
            detail_tmp.replace(detail_path)
            thumbnail_tmp.replace(thumbnail_path)
        except Exception:
            detail_tmp.unlink(missing_ok=True)
            thumbnail_tmp.unlink(missing_ok=True)
            detail_path.unlink(missing_ok=True)
            thumbnail_path.unlink(missing_ok=True)
            raise
        digest = hashlib.sha256(detail_path.read_bytes()).hexdigest()
        return ProcessedMedia(
            object_key=object_key,
            thumbnail_object_key=thumbnail_key,
            mime_type="image/jpeg",
            file_size=detail_path.stat().st_size,
            width=detail.width,
            height=detail.height,
            sha256=digest,
        )

    def delete(self, object_key: str | None) -> None:
        if not object_key:
            return
        self._public_path(object_key).unlink(missing_ok=True)
