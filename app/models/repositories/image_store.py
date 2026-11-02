"""File storage for food images. The only code that reads or writes image files.

Layout under UPLOAD_FOLDER:
  pending/<token>.<ext>          uploaded or generated, waiting for the admin to save or discard
  food/<item_id>-<uuid>.<ext>    saved images, served by the shop
"""
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from flask import current_app

from app.models.errors import ImageError

UPLOAD_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
SERVED_EXTENSIONS = UPLOAD_EXTENSIONS | {"svg"}  # svg only from the sanitised generator
TOKEN_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|jpeg|png|webp|svg)$")
FILENAME_RE = re.compile(r"^\d+-[0-9a-f]{32}\.(jpg|jpeg|png|webp|svg)$")
MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "webp": "image/webp", "svg": "image/svg+xml"}


def _matches_magic(data: bytes, ext: str) -> bool:
    if ext == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return data.startswith(b"\xff\xd8\xff")
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def extension_of(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


class ImageStore:
    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or current_app.config["UPLOAD_FOLDER"])

    @property
    def pending_dir(self) -> Path:
        return self.root / "pending"

    @property
    def food_dir(self) -> Path:
        return self.root / "food"

    @staticmethod
    def validate_upload(filename: str, data: bytes) -> str:
        """Return the normalised extension, or raise ImageError."""
        ext = extension_of(filename or "")
        if ext not in UPLOAD_EXTENSIONS:
            raise ImageError("Upload a JPG, PNG or WebP picture.")
        if not data:
            raise ImageError("The file is empty.")
        if not _matches_magic(data, ext):
            raise ImageError("The file content does not match its type. Upload a real JPG, PNG or WebP picture.")
        return "jpg" if ext == "jpeg" else ext

    def save_pending(self, data: bytes, ext: str) -> str:
        if ext not in SERVED_EXTENSIONS:
            raise ImageError("Unsupported image type.")
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        token = f"{uuid.uuid4().hex}.{ext}"
        (self.pending_dir / token).write_bytes(data)
        return token

    def pending_path(self, token: str) -> Path:
        if not TOKEN_RE.match(token or ""):
            raise ImageError("Unknown image.")
        path = self.pending_dir / token
        if not path.is_file():
            raise ImageError("The preview has expired. Please upload or generate the picture again.")
        return path

    def read_pending(self, token: str) -> bytes:
        return self.pending_path(token).read_bytes()

    def promote(self, token: str, item_id: int) -> str:
        source = self.pending_path(token)
        self.food_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{item_id}-{uuid.uuid4().hex}.{extension_of(token)}"
        os.replace(source, self.food_dir / filename)
        return filename

    def discard(self, token: str) -> None:
        try:
            self.pending_path(token).unlink()
        except ImageError:
            pass

    def food_path(self, filename: str) -> Path:
        if not FILENAME_RE.match(filename or ""):
            raise ImageError("Unknown image.")
        path = self.food_dir / filename
        if not path.is_file():
            raise ImageError("Unknown image.")
        return path

    def read_food(self, filename: str) -> bytes:
        return self.food_path(filename).read_bytes()

    def delete(self, filename: Optional[str]) -> None:
        if not filename:
            return
        try:
            self.food_path(filename).unlink()
        except ImageError:
            pass

    @staticmethod
    def mime_type(name: str) -> str:
        return MIME_TYPES[extension_of(name)]
