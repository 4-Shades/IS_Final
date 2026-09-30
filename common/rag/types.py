"""Retrieval result types, importable without the retrieval dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.schemas import SourceCitation


@dataclass(frozen=True)
class Guidance:
    prompt_block: str = ""
    sources: list[SourceCitation] = field(default_factory=list)


EMPTY = Guidance()
