import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import ImageError
from app.models.repositories import FoodItemRepository
from app.models.services.image_generator import ClaudeImageGenerator, FakeImageGenerator, sanitise_svg

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # header is enough for the type check
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'


def upload(client, item_id, data, filename):
    return client.post(f"/admin/food-items/{item_id}/image/upload",
                       data={"image": (io.BytesIO(data), filename)}, content_type="multipart/form-data")


def pending_files(app) -> list[Path]:
    folder = Path(app.config["UPLOAD_FOLDER"]) / "pending"
    return list(folder.iterdir()) if folder.exists() else []


def get_item(app, item_id):
    with app.app_context():
        return FoodItemRepository().get(item_id)


# ----------------------------------------------------------------- upload

def test_upload_goes_to_preview_without_saving(admin_client, app, food_item):
    response = upload(admin_client, food_item.id, PNG, "soup.png")

    assert response.status_code == 302 and response.headers["Location"].endswith("/image/preview")
    assert get_item(app, food_item.id).image_filename is None
    [pending] = pending_files(app)
    preview = admin_client.get(f"/admin/food-items/{food_item.id}/image/preview").get_data(as_text=True)
    assert "not saved yet" in preview and pending.name in preview

    served = admin_client.get(f"/admin/images/pending/{pending.name}")
    assert served.status_code == 200 and served.data == PNG and served.mimetype == "image/png"


def test_save_stores_image_and_shop_serves_it(admin_client, app, food_item):
    upload(admin_client, food_item.id, JPEG, "soup.JPEG")
    response = admin_client.post(f"/admin/food-items/{food_item.id}/image/save")

    assert response.status_code == 302
    filename = get_item(app, food_item.id).image_filename
    assert filename and filename.startswith(f"{food_item.id}-") and filename.endswith(".jpg")
    assert pending_files(app) == []

    served = admin_client.get(f"/images/{filename}")
    assert served.status_code == 200 and served.data == JPEG
    assert served.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert served.headers["X-Content-Type-Options"] == "nosniff"
    assert f"/images/{filename}" in admin_client.get("/").get_data(as_text=True)


def test_new_image_replaces_and_deletes_old_file(admin_client, app, food_item):
    upload(admin_client, food_item.id, PNG, "a.png")
    admin_client.post(f"/admin/food-items/{food_item.id}/image/save")
    first = get_item(app, food_item.id).image_filename

    upload(admin_client, food_item.id, JPEG, "b.jpg")
    admin_client.post(f"/admin/food-items/{food_item.id}/image/save")
    second = get_item(app, food_item.id).image_filename

    assert first != second
    assert admin_client.get(f"/images/{first}").status_code == 404
    assert admin_client.get(f"/images/{second}").status_code == 200


def test_discard_removes_pending_file(admin_client, app, food_item):
    upload(admin_client, food_item.id, PNG, "soup.png")
    admin_client.post(f"/admin/food-items/{food_item.id}/image/discard")

    assert pending_files(app) == []
    assert get_item(app, food_item.id).image_filename is None


@pytest.mark.parametrize("data, filename, message", [
    (b"MZ\x90\x00", "virus.exe", "Upload a JPG, PNG or WebP"),
    (b"not really a picture", "fake.png", "does not match its type"),
    (f"<svg {SVG_NS}/>".encode(), "drawing.svg", "Upload a JPG, PNG or WebP"),
])
def test_bad_uploads_are_rejected(admin_client, app, food_item, data, filename, message):
    response = upload(admin_client, food_item.id, data, filename)

    assert response.headers["Location"].endswith("/image")
    assert message in admin_client.get(response.headers["Location"]).get_data(as_text=True)
    assert pending_files(app) == []


def test_too_large_upload_is_refused(admin_client, food_item):
    response = upload(admin_client, food_item.id, PNG + b"\x00" * (5 * 1024 * 1024), "huge.png")

    assert response.status_code == 413


def test_image_routes_need_admin(client, customer, food_item):
    from tests.conftest import login
    login(client, customer.email)

    assert upload(client, food_item.id, PNG, "soup.png").status_code == 403
    assert client.get(f"/admin/food-items/{food_item.id}/image").status_code == 403


def test_served_image_names_are_validated(client):
    assert client.get("/images/..%2Fecommerce.sqlite").status_code == 404
    assert client.get("/images/not-an-image.txt").status_code == 404


# ----------------------------------------------------------------- AI instruction (fake generator)

def test_generate_previews_then_saves_svg(admin_client, app, food_item):
    response = admin_client.post(f"/admin/food-items/{food_item.id}/image/generate",
                                 data={"instruction": "A bowl of fish soup", "base": "none"})

    assert response.headers["Location"].endswith("/image/preview")
    [pending] = pending_files(app)
    assert pending.suffix == ".svg" and b"A bowl of fish soup" in pending.read_bytes()
    assert get_item(app, food_item.id).image_filename is None

    admin_client.post(f"/admin/food-items/{food_item.id}/image/save")
    filename = get_item(app, food_item.id).image_filename
    served = admin_client.get(f"/images/{filename}")
    assert served.mimetype == "image/svg+xml" and b"<svg" in served.data


def test_refine_sends_pending_picture_to_generator(admin_client, app, food_item):
    generator: FakeImageGenerator = app.extensions["image_generator"]
    admin_client.post(f"/admin/food-items/{food_item.id}/image/generate",
                      data={"instruction": "Fish soup", "base": "none"})
    first_svg = pending_files(app)[0].read_bytes()

    admin_client.post(f"/admin/food-items/{food_item.id}/image/generate",
                      data={"instruction": "Make the bowl blue", "base": "pending"})

    instruction, current, current_type = generator.calls[-1]
    assert instruction == "Make the bowl blue" and current == first_svg and current_type == "svg"
    assert len(pending_files(app)) == 1  # the older preview was cleaned up


def test_modify_current_sends_saved_picture(admin_client, app, food_item):
    upload(admin_client, food_item.id, PNG, "soup.png")
    admin_client.post(f"/admin/food-items/{food_item.id}/image/save")

    admin_client.post(f"/admin/food-items/{food_item.id}/image/generate",
                      data={"instruction": "Add parsley", "base": "current"})

    _, current, current_type = app.extensions["image_generator"].calls[-1]
    assert current == PNG and current_type == "png"


def test_empty_instruction_is_rejected(admin_client, app, food_item):
    response = admin_client.post(f"/admin/food-items/{food_item.id}/image/generate",
                                 data={"instruction": "  ", "base": "none"}, follow_redirects=True)

    assert "Write an instruction" in response.get_data(as_text=True)
    assert pending_files(app) == []


# ----------------------------------------------------------------- SVG sanitising

SAFE_SVG = f'<svg {SVG_NS} viewBox="0 0 10 10"><defs><linearGradient id="g"/></defs><rect fill="url(#g)" width="5" height="5"/></svg>'


def test_safe_svg_passes():
    assert sanitise_svg(SAFE_SVG.encode()) == SAFE_SVG.encode()


@pytest.mark.parametrize("svg", [
    f'<svg {SVG_NS}><script>alert(1)</script></svg>',
    f'<svg {SVG_NS} onload="alert(1)"><rect/></svg>',
    f'<svg {SVG_NS}><foreignObject><div/></foreignObject></svg>',
    f'<svg {SVG_NS}><style>rect {{ fill: red }}</style></svg>',
    f'<svg {SVG_NS} xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="https://evil.example.com/x.svg#a"/></svg>',
    f'<svg {SVG_NS}><rect fill="url(https://evil.example.com/a)"/></svg>',
    f'<svg {SVG_NS}><a href="javascript:alert(1)"><rect/></a></svg>',
    f'<!DOCTYPE svg [<!ENTITY x "y">]><svg {SVG_NS}>&x;</svg>',
    '<html><body/></html>',
    'not xml at all',
])
def test_unsafe_svg_is_rejected(svg):
    with pytest.raises(ImageError):
        sanitise_svg(svg.encode())


# ----------------------------------------------------------------- Claude generator (stub client, no network)

class StubMessages:
    def __init__(self, response):
        self.response, self.kwargs = response, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def stub_client(text, stop_reason="end_turn"):
    response = SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])
    messages = StubMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_claude_generator_builds_request_and_extracts_svg():
    client, messages = stub_client(f"Here you go:\n```svg\n{SAFE_SVG}\n```")
    generator = ClaudeImageGenerator(client=client)

    result = generator.generate("Fish soup", current=b"<svg/>", current_type="svg")

    assert result == SAFE_SVG.encode()
    kwargs = messages.kwargs
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["fallbacks"] == "default" and kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    texts = [block["text"] for block in kwargs["messages"][0]["content"]]
    assert any("<svg/>" in t for t in texts) and any("Fish soup" in t for t in texts)


def test_claude_generator_sends_photo_as_image_block():
    client, messages = stub_client(SAFE_SVG)
    ClaudeImageGenerator(client=client).generate("Make it a drawing", current=PNG, current_type="png")

    image_block = messages.kwargs["messages"][0]["content"][0]
    assert image_block["type"] == "image" and image_block["source"]["media_type"] == "image/png"


def test_claude_generator_without_credentials_gives_clear_error():
    class NoCredentials:
        def create(self, **kwargs):
            raise TypeError('"Could not resolve authentication method. Expected one of api_key, auth_token, ..."')

    client = SimpleNamespace(beta=SimpleNamespace(messages=NoCredentials()))
    with pytest.raises(ImageError, match="ANTHROPIC_API_KEY"):
        ClaudeImageGenerator(client=client).generate("Fish soup")


@pytest.mark.parametrize("text, stop_reason, message", [
    ("", "refusal", "declined"),
    ("<svg", "max_tokens", "too complex"),
    ("Sorry, I cannot draw that.", "end_turn", "did not return a picture"),
    (f"<svg {SVG_NS}><script>x</script></svg>", "end_turn", "forbidden element"),
])
def test_claude_generator_errors_become_image_errors(text, stop_reason, message):
    client, _ = stub_client(text, stop_reason)

    with pytest.raises(ImageError, match=message):
        ClaudeImageGenerator(client=client).generate("Anything")
