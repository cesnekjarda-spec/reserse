from __future__ import annotations

import re
from html import escape
from markupsafe import Markup

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r'(?<!["\'=])(https?://[^\s<]+)')


def render_rich_text(value: str | None) -> Markup:
    text = value or ""
    placeholders: dict[str, str] = {}

    def _store_link(match: re.Match[str]) -> str:
        label = escape(match.group(1))
        url = escape(match.group(2), quote=True)
        token = f"__LINK_{len(placeholders)}__"
        placeholders[token] = f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'
        return token

    text = _MARKDOWN_LINK_RE.sub(_store_link, text)
    text = escape(text)

    def _bare_url(match: re.Match[str]) -> str:
        url = match.group(1)
        cleaned = url.rstrip(').,;!?:')
        trailing = url[len(cleaned):]
        safe = escape(cleaned, quote=True)
        return f'<a href="{safe}" target="_blank" rel="noopener">{safe}</a>{trailing}'

    text = _BARE_URL_RE.sub(_bare_url, text)
    for token, html in placeholders.items():
        text = text.replace(token, html)
    text = text.replace('\n', '<br>')
    return Markup(text)
