"""Create or modify food pictures from an admin's written instruction.

Claude cannot produce photos, so the Claude generator returns an SVG illustration.
All generated SVG is treated as untrusted and passed through `sanitise_svg`.
"""
import base64
import re
import xml.etree.ElementTree as ET
from html import escape
from typing import Optional, Protocol

from app.models.errors import ImageError

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
MAX_SVG_BYTES = 200_000

ALLOWED_TAGS = {
    "svg", "g", "defs", "title", "desc", "path", "rect", "circle", "ellipse", "line",
    "polyline", "polygon", "text", "tspan", "linearGradient", "radialGradient", "stop",
    "clipPath", "mask", "pattern", "use", "symbol",
}


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def sanitise_svg(data: bytes) -> bytes:
    """Return the SVG unchanged if it only uses safe drawing features, otherwise raise ImageError."""
    if len(data) > MAX_SVG_BYTES:
        raise ImageError("The generated image is too large.")
    text = data.decode("utf-8", errors="strict") if isinstance(data, bytes) else data
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.IGNORECASE):
        raise ImageError("The generated image contains unsupported content.")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ImageError("The generated image is not valid SVG.") from None
    if _local(root.tag) != "svg":
        raise ImageError("The generated image is not an SVG.")
    for element in root.iter():
        if _local(element.tag) not in ALLOWED_TAGS:
            raise ImageError(f"The generated image uses a forbidden element: <{_local(element.tag)}>.")
        for name, value in element.attrib.items():
            attr = _local(name).lower()
            if attr.startswith("on"):
                raise ImageError("The generated image contains script attributes.")
            if attr == "href" and not value.startswith("#"):
                raise ImageError("The generated image links to an external resource.")
            lowered = value.lower()
            urls = re.findall(r"url\(\s*['\"]?([^)'\"]*)", lowered)
            if "javascript:" in lowered or any(not u.startswith("#") for u in urls):
                raise ImageError("The generated image refers to an external resource.")
    return text.encode("utf-8")


class ImageGenerator(Protocol):
    def generate(self, instruction: str, current: Optional[bytes] = None,
                 current_type: Optional[str] = None) -> bytes:
        """Return SVG bytes. `current` is an existing image to modify, `current_type` its file extension."""
        ...


class FakeImageGenerator:
    """Offline generator for tests and for running without an API key."""

    def __init__(self):
        self.calls: list[tuple[str, Optional[bytes], Optional[str]]] = []

    def generate(self, instruction, current=None, current_type=None) -> bytes:
        self.calls.append((instruction, current, current_type))
        label = escape(instruction[:60])
        svg = (f'<svg xmlns="{SVG_NS}" viewBox="0 0 400 300" width="400" height="300">'
               f'<rect width="400" height="300" fill="#f3efe6"/>'
               f'<circle cx="200" cy="130" r="70" fill="#c8a165"/>'
               f'<text x="200" y="260" font-size="16" text-anchor="middle" fill="#333">{label}</text>'
               f'</svg>')
        return sanitise_svg(svg.encode("utf-8"))


SYSTEM_PROMPT = """You draw food illustrations for the menu of Ekte Mat, a catering company in Bergen, Norway.
Reply with one complete SVG document and nothing else.
Rules:
- Root element <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">.
- Use only shapes, paths, text and gradients. No <script>, <style>, <foreignObject>, <image>,
  event attributes, external links or fonts.
- Appetising, clean flat illustration style with warm colours; no text unless asked for.
- Keep the file under 50 KB."""

RASTER_MEDIA_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}


class ClaudeImageGenerator:
    MODEL = "claude-opus-5-5"

    def __init__(self, client=None):
        # Created on first use, so the app starts even when no API key is configured.
        self._client = client

    @property
    def client(self):
        if self._client is None:
            import anthropic
            try:
                self._client = anthropic.Anthropic(timeout=120.0, max_retries=1)
            except anthropic.AnthropicError:
                raise ImageError("Image generation is not set up: set ANTHROPIC_API_KEY in .env.") from None
        return self._client

    def _content(self, instruction: str, current: Optional[bytes], current_type: Optional[str]) -> list:
        content = []
        if current is not None and current_type == "svg":
            content.append({"type": "text", "text": "Current picture (SVG):\n" + current.decode("utf-8")})
            content.append({"type": "text", "text": f"Modify the picture as follows: {instruction}"})
        elif current is not None and current_type in RASTER_MEDIA_TYPES:
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": RASTER_MEDIA_TYPES[current_type],
                "data": base64.standard_b64encode(current).decode("ascii")}})
            content.append({"type": "text", "text": "Draw an SVG illustration based on this photo. "
                                                    f"Instruction: {instruction}"})
        else:
            content.append({"type": "text", "text": f"Draw this: {instruction}"})
        return content

    def generate(self, instruction, current=None, current_type=None) -> bytes:
        import anthropic

        try:
            response = self.client.beta.messages.create(
                model=self.MODEL,
                max_tokens=16000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                output_config={"effort": "medium"},
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": self._content(instruction, current, current_type)}],
            )
        except anthropic.AuthenticationError:
            raise ImageError("Image generation is not set up: the Anthropic API key is missing or invalid.") from None
        except anthropic.RateLimitError:
            raise ImageError("The image service is busy. Please try again in a minute.") from None
        except anthropic.APIConnectionError:
            raise ImageError("Could not reach the image service. Check the internet connection.") from None
        except anthropic.APIStatusError as e:
            raise ImageError(f"The image service returned an error ({e.status_code}).") from None
        except anthropic.AnthropicError:
            raise ImageError("Image generation is not set up: no Anthropic credentials found.") from None
        except TypeError as e:
            # SDK 2.x raises TypeError("Could not resolve authentication method ...") when no key is configured.
            if "authentication" not in str(e):
                raise
            raise ImageError("Image generation is not set up: set ANTHROPIC_API_KEY in .env.") from None

        if response.stop_reason == "refusal":
            raise ImageError("The image service declined this instruction. Try wording it differently.")
        if response.stop_reason == "max_tokens":
            raise ImageError("The picture became too complex. Try a simpler instruction.")
        text = "".join(block.text for block in response.content if block.type == "text")
        match = re.search(r"<svg\b.*</svg>", text, re.DOTALL)
        if not match:
            raise ImageError("The image service did not return a picture. Please try again.")
        return sanitise_svg(match.group(0).encode("utf-8"))


def create_image_generator(kind: str) -> ImageGenerator:
    if kind == "fake":
        return FakeImageGenerator()
    if kind == "claude":
        return ClaudeImageGenerator()
    raise ValueError(f"Unknown IMAGE_GENERATOR: {kind!r} (use 'claude' or 'fake')")
