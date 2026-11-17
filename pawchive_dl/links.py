"""HTML link extraction and per-creator Markdown link index updates."""

from __future__ import annotations

import os
import re
import tempfile
import threading
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, object]] = []
        self.open_anchors: list[dict[str, object] | None] = []
        self.active_anchors: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        has_href = any(name.lower() == "href" for name, _ in attrs)
        href = next((value for name, value in attrs if name.lower() == "href"), None)
        anchor: dict[str, object] | None = {"href": href or "", "text": []} if has_href else None
        self.open_anchors.append(anchor)
        if anchor is not None:
            self.anchors.append(anchor)
            self.active_anchors.append(anchor)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() == "a":
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a":
            return
        if not self.open_anchors:
            return
        anchor = self.open_anchors.pop()
        if anchor is not None and anchor in self.active_anchors:
            self.active_anchors.remove(anchor)

    def handle_data(self, data: str) -> None:
        for anchor in self.active_anchors:
            text = anchor["text"]
            assert isinstance(text, list)
            text.append(data)


def extract_links(content_html: str, post_url: str) -> list[tuple[str, str]]:
    """Return unique (display text, absolute URL) pairs in source order."""
    parser = _AnchorParser()
    parser.feed(content_html)
    parser.close()

    links: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for anchor in parser.anchors:
        if anchor is None:
            continue
        href = str(anchor["href"]).strip()
        try:
            target_url = urljoin(post_url, href)
            parsed_url = urlsplit(target_url)
            if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_url.netloc:
                continue
            # Accessing hostname validates malformed IPv6 and port syntax.
            if not parsed_url.hostname:
                continue
        except ValueError:
            continue

        text_parts = anchor["text"]
        assert isinstance(text_parts, list)
        display_text = " ".join("".join(text_parts).split()) or target_url
        item = (display_text, target_url)
        if item not in seen:
            links.append(item)
            seen.add(item)
    return links


_LOCKS_GUARD = threading.Lock()
_FILE_LOCKS: dict[str, threading.Lock] = {}
_MARKER_PATTERN = re.compile(r"(?m)^<!-- pawchive-dl:post:[^\r\n]+ -->[ \t]*$")


def _file_lock(path: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(path, threading.Lock())


def _post_marker(service: str, creator_id: str, post_id: str) -> str:
    return f"<!-- pawchive-dl:post:{service}:{creator_id}:{post_id} -->"


def _escape_markdown_text(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>])", r"\\\1", text).replace("\n", " ")


def _escape_markdown_url(url: str) -> str:
    return url.replace("\\", "%5C").replace("(", "%28").replace(")", "%29").replace(" ", "%20")


def _render_post_section(
    marker: str,
    title: str,
    post_id: str,
    original_url: str,
    links: list[tuple[str, str]],
) -> str:
    lines = [marker, f"## {_escape_markdown_text(title) or '(untitled)'}", "", f"- Post ID: {post_id}", f"- Original URL: {original_url}", "", "### Links"]
    if links:
        lines.extend(f"- [{_escape_markdown_text(text)}]({_escape_markdown_url(url)})" for text, url in links)
    else:
        lines.append("- No links")
    lines.extend(["", "---"])
    return "\n".join(lines)


def update_links_file(
    path: str,
    *,
    service: str,
    creator_id: str,
    post_id: str,
    title: str,
    original_url: str,
    links: list[tuple[str, str]],
) -> None:
    """Atomically add, replace, or remove one post section under a per-file lock."""
    absolute_path = os.path.abspath(path)
    marker = _post_marker(service, creator_id, post_id)
    with _file_lock(absolute_path):
        target = Path(absolute_path)
        content = target.read_text(encoding="utf-8") if target.exists() else "# Pawchive Links\n"
        markers = list(_MARKER_PATTERN.finditer(content))

        if markers:
            header = content[: markers[0].start()].strip() or "# Pawchive Links"
            sections: OrderedDict[str, str] = OrderedDict()
            for index, marker_match in enumerate(markers):
                end = markers[index + 1].start() if index + 1 < len(markers) else len(content)
                section = content[marker_match.start() : end].strip()
                section = re.sub(r"\n*---\s*$", "", section).rstrip()
                sections.setdefault(marker_match.group(0), section)
        else:
            header = content.strip() or "# Pawchive Links"
            sections = OrderedDict()

        if links:
            sections[marker] = _render_post_section(marker, title, post_id, original_url, links)
        else:
            sections.pop(marker, None)

        output = header.rstrip() + "\n"
        if sections:
            output += "\n" + "\n\n".join(sections.values()) + "\n"

        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = temporary_file.name
                temporary_file.write(output)
            os.replace(temporary_path, target)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
