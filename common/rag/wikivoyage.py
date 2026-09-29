"""Fetch Wikivoyage articles and split them into top-level sections."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

API_URL = "https://en.wikivoyage.org/w/api.php"
LICENSE = "CC BY-SA 4.0"
# Wikimedia asks API clients to identify themselves with a contact URL.
USER_AGENT = "IS_Final-travel-planner/0.1 (https://github.com/4-Shades/IS_Final)"
INTRO_SECTION = "Overview"

_HEADING = re.compile(r"^(=+)\s*(.+?)\s*\1\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    revision_id: int
    sections: dict[str, str]


class ArticleNotFound(LookupError):
    pass


def split_sections(extract: str) -> dict[str, str]:
    # Deeper headings stay inside their level-2 parent, so "Get in" keeps "By plane".
    sections: dict[str, list[str]] = {INTRO_SECTION: []}
    current = INTRO_SECTION
    position = 0
    for match in _HEADING.finditer(extract):
        sections.setdefault(current, []).append(extract[position:match.start()])
        level, name = len(match.group(1)), match.group(2)
        if level == 2:
            current = name
        else:
            sections.setdefault(current, []).append(f"\n{name}\n")
        position = match.end()
    sections.setdefault(current, []).append(extract[position:])

    cleaned = {}
    for name, parts in sections.items():
        text = re.sub(r"\n{3,}", "\n\n", "".join(parts)).strip()
        if text:
            cleaned[name] = text
    return cleaned


def parse_response(payload: dict) -> Article:
    pages = payload.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing") or "extract" not in pages[0]:
        raise ArticleNotFound("no Wikivoyage article")
    page = pages[0]
    revisions = page.get("revisions") or [{}]
    return Article(
        title=page["title"],
        url=page["fullurl"],
        revision_id=int(revisions[0].get("revid") or page.get("lastrevid") or 0),
        sections=split_sections(page["extract"]),
    )


def fetch_article(title: str, *, client: httpx.Client) -> Article:
    response = client.get(
        API_URL,
        params={
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "extracts|revisions|info",
            "titles": title,
            "redirects": "1",
            "explaintext": "1",
            "exsectionformat": "wiki",
            "rvprop": "ids",
            "inprop": "url",
        },
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    try:
        return parse_response(response.json())
    except ArticleNotFound as exc:
        raise ArticleNotFound(f"no Wikivoyage article for {title!r}") from exc
