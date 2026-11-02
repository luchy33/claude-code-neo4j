"""Storage for food images. The only code that reads or writes image data.

Images are (:Image {name, data, pending, created_at}) nodes in Neo4j:
  pending: <token>.<ext>          uploaded or generated, waiting for the admin to save or discard
  saved:   <item_id>-<uuid>.<ext> served by the shop, linked from the dish with HAS_IMAGE
"""
import re
import uuid
from datetime import datetime, timedelta

from app.models.errors import ImageError
from app.models.repositories.db import query, to_db_time

UPLOAD_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
SERVED_EXTENSIONS = UPLOAD_EXTENSIONS | {"svg"}  # svg only from the sanitised generator
TOKEN_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|jpeg|png|webp|svg)$")
FILENAME_RE = re.compile(r"^\d+-[0-9a-f]{32}\.(jpg|jpeg|png|webp|svg)$")
MIME_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
              "webp": "image/webp", "svg": "image/svg+xml"}
PENDING_LIFETIME = timedelta(days=1)  # previews the admin never saved or discarded are removed after this


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
        now = to_db_time(datetime.now())
        query("MATCH (i:Image {pending: true}) WHERE i.created_at < $cutoff DETACH DELETE i",
              cutoff=now - PENDING_LIFETIME)
        token = f"{uuid.uuid4().hex}.{ext}"
        query("CREATE (:Image {name: $name, data: $data, pending: true, created_at: $now})",
              name=token, data=data, now=now)
        return token

    def read_pending(self, token: str) -> bytes:
        if not TOKEN_RE.match(token or ""):
            raise ImageError("Unknown image.")
        records = query("MATCH (i:Image {name: $name, pending: true}) RETURN i.data AS data", name=token)
        if not records:
            raise ImageError("The preview has expired. Please upload or generate the picture again.")
        return records[0]["data"]

    def promote(self, token: str, item_id: int) -> str:
        """Turn a pending image into a saved one. FoodItemRepository.set_image links it to the dish."""
        if not TOKEN_RE.match(token or ""):
            raise ImageError("Unknown image.")
        filename = f"{item_id}-{uuid.uuid4().hex}.{extension_of(token)}"
        if not query("MATCH (i:Image {name: $token, pending: true}) SET i.name = $filename, i.pending = false"
                     " RETURN i.name AS name", token=token, filename=filename):
            raise ImageError("The preview has expired. Please upload or generate the picture again.")
        return filename

    def discard(self, token: str) -> None:
        if TOKEN_RE.match(token or ""):
            query("MATCH (i:Image {name: $name, pending: true}) DETACH DELETE i", name=token)

    def read_food(self, filename: str) -> bytes:
        if not FILENAME_RE.match(filename or ""):
            raise ImageError("Unknown image.")
        records = query("MATCH (i:Image {name: $name, pending: false}) RETURN i.data AS data", name=filename)
        if not records:
            raise ImageError("Unknown image.")
        return records[0]["data"]

    def delete(self, filename) -> None:
        if filename and FILENAME_RE.match(filename):
            query("MATCH (i:Image {name: $name, pending: false}) DETACH DELETE i", name=filename)

    @staticmethod
    def mime_type(name: str) -> str:
        return MIME_TYPES[extension_of(name)]
