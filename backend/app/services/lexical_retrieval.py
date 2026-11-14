"""Shared literal matching, not Chinese word segmentation or semantic inference."""

from __future__ import annotations

import re
import unicodedata


_PARTS = re.compile(r"[a-z0-9_]+(?:[.-][a-z0-9_]+)*|[\u3400-\u4dbf\u4e00-\u9fff]+")
_CHINESE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+\Z")


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


class LexicalQuery:
    """Prepare a query once; score eligible texts using fixed-width literal terms.

    Chinese runs contribute overlapping two/three-character fragments. Latin
    identifiers and numeric strings remain whole. No corpus-wide statistics or
    external dependency is used, so another scope cannot influence this score.
    """

    def __init__(self, query: str) -> None:
        self._parts = tuple(dict.fromkeys(_PARTS.findall(_normalize(query))))
        self._mixed = any(_CHINESE.fullmatch(part) for part in self._parts) and any(
            not _CHINESE.fullmatch(part) for part in self._parts
        )
        terms: list[str] = []
        for part in self._parts:
            if _CHINESE.fullmatch(part) and len(part) > 1:
                terms.extend(part[start:start + width] for width in (2, 3) for start in range(len(part) - width + 1))
            else:
                terms.append(part)
        self._terms = tuple(dict.fromkeys(terms))
        self._weight = sum(min(8, len(term)) for term in self._terms)

    def score(self, content: str) -> float:
        text = _normalize(content)
        matched = tuple(term for term in self._terms if term in text)
        if not matched:
            return 0.0
        if self._mixed:
            words = set(_PARTS.findall(text))
            complete_literal = any(
                part in words if not _CHINESE.fullmatch(part) else len(part) >= 2 and part in text
                for part in self._parts
            )
            # A lone short fragment must not turn a weak vector candidate into
            # apparent two-route corroboration for an unrelated identifier.
            # Multiple Chinese fragments still support natural mixed questions
            # even when the document does not repeat their English label.
            chinese_pairs = sum(len(term) == 2 and bool(_CHINESE.fullmatch(term)) for term in matched)
            if not complete_literal and chinese_pairs < 2:
                return 0.0
        # Presence saturates at one: repeating generic words earns no extra
        # coverage. Longer literal fragments/identifiers carry bounded weight.
        coverage = sum(min(8, len(term)) for term in matched) / self._weight
        # A small bounded concentration factor breaks broad/verbose ties;
        # coverage contributes at least 90% of the score in every document.
        concentration = min(1.0, sum(len(term) for term in matched) / len(text))
        return round(coverage * (0.9 + 0.1 * concentration), 6)
