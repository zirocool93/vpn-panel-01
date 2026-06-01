"""Service helpers for editing bot pages from the Web admin."""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urlparse

from bot.utils.page_renderer import get_page_data
from database.connection import get_db
from database.db_pages import get_page, update_page_custom


TELEGRAM_ALLOWED_TAGS = {
    "a", "b", "blockquote", "code", "del", "em", "i", "ins", "pre",
    "s", "span", "strike", "strong", "tg-emoji", "u",
}
TELEGRAM_VOID_TAGS = {"br"}
BUTTON_ACTION_TYPES = {"internal", "system", "url"}
BUTTON_COLORS = {"primary", "secondary", "success", "danger"}


@dataclass
class PageValidationResult:
    ok: bool
    errors: list[str]
    normalized_buttons: Optional[str] = None


class TelegramHTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in TELEGRAM_VOID_TAGS:
            return
        if tag not in TELEGRAM_ALLOWED_TAGS:
            self.errors.append(f"Unsupported HTML tag: <{tag}>")
            return
        attrs_map = dict(attrs)
        if tag == "a":
            href = attrs_map.get("href", "")
            if not _is_safe_url(href):
                self.errors.append("Link href must use http://, https:// or tg://")
        elif tag == "span":
            if attrs_map.get("class") != "tg-spoiler":
                self.errors.append('Only <span class="tg-spoiler"> is allowed')
        elif tag == "tg-emoji":
            if not attrs_map.get("emoji-id"):
                self.errors.append('Tag <tg-emoji> requires emoji-id')
        elif attrs:
            self.errors.append(f"Tag <{tag}> does not support attributes here")
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in TELEGRAM_VOID_TAGS:
            return
        if tag not in TELEGRAM_ALLOWED_TAGS:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"Unexpected closing tag: </{tag}>")
            return
        self.stack.pop()

    def close(self) -> None:
        super().close()
        for tag in reversed(self.stack):
            self.errors.append(f"Unclosed HTML tag: <{tag}>")


class TelegramPreviewRenderer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        attrs_map = dict(attrs)
        if tag in TELEGRAM_VOID_TAGS:
            self.parts.append("<br>")
            return
        if tag not in TELEGRAM_ALLOWED_TAGS:
            self.parts.append(html.escape(self.get_starttag_text() or ""))
            return
        if tag == "a":
            href = attrs_map.get("href", "")
            if _is_safe_url(href):
                self.parts.append(f'<a href="{html.escape(href, quote=True)}" rel="noreferrer">')
                self.stack.append(tag)
                return
        elif tag == "span" and attrs_map.get("class") == "tg-spoiler":
            self.parts.append('<span class="tg-spoiler">')
            self.stack.append(tag)
            return
        elif tag == "tg-emoji":
            self.parts.append('<span class="tg-emoji">')
            self.stack.append(tag)
            return
        elif not attrs:
            self.parts.append(f"<{tag}>")
            self.stack.append(tag)
            return
        self.parts.append(html.escape(self.get_starttag_text() or ""))

    def handle_endtag(self, tag: str) -> None:
        if tag not in TELEGRAM_ALLOWED_TAGS or not self.stack:
            self.parts.append(html.escape(f"</{tag}>"))
            return
        if self.stack[-1] != tag:
            self.parts.append(html.escape(f"</{tag}>"))
            return
        self.stack.pop()
        self.parts.append("</span>" if tag in {"span", "tg-emoji"} else f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(html.escape(data).replace("\n", "<br>"))

    def get_html(self) -> str:
        while self.stack:
            tag = self.stack.pop()
            self.parts.append("</span>" if tag in {"span", "tg-emoji"} else f"</{tag}>")
        return "".join(self.parts)


def list_pages() -> list[dict[str, Any]]:
    """Return all rows from the existing pages table."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT page_key, text_default, image_default, buttons_default,
                   text_custom, image_custom, buttons_custom, updated_at
            FROM pages
            ORDER BY page_key
            """
        ).fetchall()
    pages = [dict(row) for row in rows]
    for page in pages:
        page["has_text_custom"] = bool(page.get("text_custom"))
        page["has_image_custom"] = bool(page.get("image_custom"))
        page["has_buttons_custom"] = bool(page.get("buttons_custom"))
    return pages


def get_page_full(page_key: str) -> Optional[dict[str, Any]]:
    row = get_page(page_key)
    if not row:
        return None
    effective = get_page_data(page_key) or {"text": "", "image": None, "buttons": []}
    result = dict(row)
    result["effective_text"] = effective["text"]
    result["effective_image"] = effective["image"]
    result["effective_buttons"] = effective["buttons"]
    result["buttons_default_pretty"] = _pretty_buttons(result.get("buttons_default"))
    result["buttons_custom_pretty"] = _pretty_buttons(result.get("buttons_custom"))
    result["effective_buttons_pretty"] = json.dumps(effective["buttons"], ensure_ascii=False, indent=2)
    result["preview_html"] = render_telegram_html_preview(effective["text"])
    return result


def update_page_from_web(page_key: str, text: str, image: str, buttons: str) -> PageValidationResult:
    result = validate_page_payload(text, image, buttons)
    if not result.ok:
        return result
    image_value = image.strip()
    buttons_value = result.normalized_buttons if buttons.strip() else ""
    update_page_custom(page_key, text=text, image=image_value, buttons=buttons_value)
    return result


def reset_page_custom_field(page_key: str, field: str) -> None:
    allowed = {"text": "text_custom", "image": "image_custom", "buttons": "buttons_custom"}
    column = allowed.get(field)
    if not column:
        raise ValueError("Unknown page custom field")
    with get_db() as conn:
        conn.execute(f"UPDATE pages SET {column} = NULL, updated_at = CURRENT_TIMESTAMP WHERE page_key = ?", (page_key,))


def validate_page_payload(text: str, image: str, buttons: str) -> PageValidationResult:
    errors: list[str] = []
    errors.extend(validate_telegram_html(text))
    image_error = validate_image_value(image.strip() or None)
    if image_error:
        errors.append(image_error)
    normalized_buttons: Optional[str] = None
    if buttons.strip():
        button_result = validate_buttons_json(buttons)
        errors.extend(button_result.errors)
        normalized_buttons = button_result.normalized_buttons
    return PageValidationResult(ok=not errors, errors=errors, normalized_buttons=normalized_buttons)


def validate_telegram_html(text: str) -> list[str]:
    parser = TelegramHTMLValidator()
    try:
        parser.feed(text or "")
        parser.close()
    except Exception as exc:
        return [f"Invalid HTML: {exc}"]
    return parser.errors


def validate_image_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    lower = value.lower()
    if lower.startswith(("javascript:", "data:", "file:")):
        return "Image must not use javascript:, data: or file: scheme"
    parsed = urlparse(value)
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"}:
            return "Image URL must use http:// or https://"
        if not parsed.netloc:
            return "Image URL must include host"
        return None
    if any(part in value for part in ("/", "\\", "..")):
        return "Image must be a URL or Telegram file_id, not a local path"
    return None


def validate_buttons_json(raw: str) -> PageValidationResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return PageValidationResult(False, [f"Buttons JSON error at line {exc.lineno}, column {exc.colno}: {exc.msg}"])
    if not isinstance(data, list):
        return PageValidationResult(False, ["Buttons JSON must be an array"])

    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, button in enumerate(data):
        prefix = f"Button #{index + 1}"
        if not isinstance(button, dict):
            errors.append(f"{prefix} must be an object")
            continue
        button_id = str(button.get("id") or "").strip()
        label = str(button.get("label") or "").strip()
        action_type = str(button.get("action_type") or "").strip()
        if not button_id:
            errors.append(f"{prefix}: id is required")
        elif button_id in seen_ids:
            errors.append(f"{prefix}: duplicate id '{button_id}'")
        seen_ids.add(button_id)
        if not label:
            errors.append(f"{prefix}: label is required")
        if action_type not in BUTTON_ACTION_TYPES:
            errors.append(f"{prefix}: action_type must be internal, system or url")
        if action_type in {"internal", "url"} and not str(button.get("action_value") or "").strip():
            errors.append(f"{prefix}: action_value is required for {action_type}")
        if action_type == "url" and not _is_safe_url(str(button.get("action_value") or "")):
            errors.append(f"{prefix}: url action_value must use http://, https:// or tg://")
        for numeric in ("row", "col"):
            if not isinstance(button.get(numeric), int) or button.get(numeric) < 0:
                errors.append(f"{prefix}: {numeric} must be a non-negative integer")
        if "is_hidden" in button and not isinstance(button.get("is_hidden"), bool):
            errors.append(f"{prefix}: is_hidden must be true or false")
        if button.get("color") and button.get("color") not in BUTTON_COLORS:
            errors.append(f"{prefix}: color must be one of {', '.join(sorted(BUTTON_COLORS))}")
    normalized = json.dumps(data, ensure_ascii=False, indent=2) if not errors else None
    return PageValidationResult(ok=not errors, errors=errors, normalized_buttons=normalized)


def render_telegram_html_preview(text: str) -> str:
    parser = TelegramPreviewRenderer()
    try:
        parser.feed(text or "")
        return parser.get_html()
    except Exception:
        return html.escape(text or "").replace("\n", "<br>")


def _pretty_buttons(raw: Optional[str]) -> str:
    if not raw:
        return ""
    try:
        return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return raw


def _is_safe_url(value: str) -> bool:
    parsed = urlparse(value or "")
    return parsed.scheme in {"http", "https", "tg"} and bool(parsed.netloc or parsed.scheme == "tg")
