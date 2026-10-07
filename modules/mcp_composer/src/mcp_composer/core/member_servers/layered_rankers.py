"""
Catalog ranking adapters for tool discovery.

``Bm25Ranker`` and ``TfidfRanker`` implement the same score port; configuration
(``tool_discovery_ranker`` / ``MCP_TOOL_DISCOVERY_RANKER``) selects which adapter
``rank_entries`` uses.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False
    if not TYPE_CHECKING:
        TfidfVectorizer = None  # type: ignore[misc, assignment]
        cosine_similarity = None  # type: ignore[misc, assignment]

# Okapi BM25 parameters (classic defaults).
_BM25_K1 = 1.5
_BM25_B = 0.75
_CAMEL_BOUNDARY = re.compile(
    r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|\d+"
)
_ALNUM_RUNS = re.compile(r"[A-Za-z0-9]+")

# Config name: tool_discovery_ranker
# Env: MCP_TOOL_DISCOVERY_RANKER = bm25 | tfidf | bm25_fallback (default)
TOOL_DISCOVERY_RANKER = "tool_discovery_ranker"
ENV_RANKER = "MCP_TOOL_DISCOVERY_RANKER"
DEFAULT_RANKER = "bm25_fallback"
VALID_RANKERS = frozenset({"bm25", "tfidf", "bm25_fallback"})


@runtime_checkable
class CatalogRanker(Protocol):
    """Port: score each corpus text against a query (higher is better)."""

    def score(self, query: str, corpus_texts: Sequence[str]) -> list[float]:
        """Return one score per corpus entry (same length as ``corpus_texts``)."""


def _tokenize_identifier(text: str) -> list[str]:
    """
    Tokenize for BM25: split snake/kebab and camelCase/PascalCase.

    Keeps alphanumeric tokens of length >= 2 (lowercased). Example:
    ``getDatabaseSecurityPolicies`` → ``get``, ``database``, ``security``,
    ``policies``.
    """
    if not text:
        return []
    tokens: list[str] = []
    for run in _ALNUM_RUNS.findall(text):
        pieces = _CAMEL_BOUNDARY.findall(run) or [run]
        for piece in pieces:
            token = piece.lower()
            if len(token) >= 2:
                tokens.append(token)
    return tokens


def _bm25_scores(
    query_tokens: list[str],
    docs_tokens: list[list[str]],
    *,
    k1: float = _BM25_K1,
    b: float = _BM25_B,
) -> list[float]:
    """Okapi BM25 scores for each document given pre-tokenized query/docs."""
    n_docs = len(docs_tokens)
    if n_docs == 0 or not query_tokens:
        return [0.0] * n_docs

    doc_lens = [len(doc) for doc in docs_tokens]
    avgdl = sum(doc_lens) / n_docs
    doc_tfs = [Counter(doc) for doc in docs_tokens]

    df: dict[str, int] = {}
    for tf in doc_tfs:
        for term in tf:
            df[term] = df.get(term, 0) + 1

    scores = [0.0] * n_docs
    for term in dict.fromkeys(query_tokens):
        n_qi = df.get(term, 0)
        if n_qi == 0:
            continue
        idf = math.log(1.0 + (n_docs - n_qi + 0.5) / (n_qi + 0.5))
        for i, tf in enumerate(doc_tfs):
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            dl = doc_lens[i] or 1
            denom = freq + k1 * (1.0 - b + b * dl / avgdl)
            scores[i] += idf * (freq * (k1 + 1.0)) / denom
    return scores


def _substring_score(query: str, text: str) -> float:
    q = query.lower().strip()
    t = text.lower()
    if not q:
        return 0.0
    if q == t or q in t:
        return 1.0
    q_parts = [p for p in q.replace("-", " ").replace("_", " ").split() if p]
    if not q_parts:
        return 0.0
    hits = sum(1 for p in q_parts if p in t)
    return hits / len(q_parts) if hits else 0.0


class Bm25Ranker:
    """Okapi BM25 over camelCase/snake_case-aware tokens."""

    def score(self, query: str, corpus_texts: Sequence[str]) -> list[float]:
        query_tokens = _tokenize_identifier(query)
        docs_tokens = [_tokenize_identifier(text) for text in corpus_texts]
        return _bm25_scores(query_tokens, docs_tokens)


class TfidfRanker:
    """Char n-gram TF-IDF; substring scoring if sklearn is unavailable."""

    def score(self, query: str, corpus_texts: Sequence[str]) -> list[float]:
        texts = list(corpus_texts)
        if not texts:
            return []
        if _SKLEARN_AVAILABLE:
            try:
                vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))
                vectors = vectorizer.fit_transform([query] + texts)
                similarities = cosine_similarity(vectors[0], vectors[1:]).flatten()
                return [float(s) for s in similarities]
            except ValueError:
                pass
        return [_substring_score(query, text) for text in texts]


class Bm25FallbackRanker:
    """BM25 first; TF-IDF only when BM25 yields no positive scores."""

    def __init__(
        self,
        primary: CatalogRanker | None = None,
        fallback: CatalogRanker | None = None,
    ) -> None:
        self._primary = primary or Bm25Ranker()
        self._fallback = fallback or TfidfRanker()

    def score(self, query: str, corpus_texts: Sequence[str]) -> list[float]:
        primary_scores = self._primary.score(query, corpus_texts)
        if any(s > 0 for s in primary_scores):
            return primary_scores
        return self._fallback.score(query, corpus_texts)


def normalize_ranker_name(name: str | None) -> str:
    """Map config/env value to a known ranker id; unknown → default."""
    raw = (name if name is not None else os.getenv(ENV_RANKER, DEFAULT_RANKER)) or ""
    cleaned = raw.strip().lower().replace("-", "_")
    aliases = {
        "bm25_then_tfidf": "bm25_fallback",
        "hybrid": "bm25_fallback",
        "idf": "tfidf",
        "tf_idf": "tfidf",
    }
    cleaned = aliases.get(cleaned, cleaned)
    if cleaned not in VALID_RANKERS:
        if cleaned:
            logger.warning(
                "Unknown %s=%r; using %s",
                ENV_RANKER,
                raw,
                DEFAULT_RANKER,
            )
        return DEFAULT_RANKER
    return cleaned


def resolve_ranker(name: str | None = None) -> CatalogRanker:
    """
    Build the configured tool-discovery ranker adapter.

    Config key ``tool_discovery_ranker`` / env ``MCP_TOOL_DISCOVERY_RANKER``:
    - ``bm25`` — Okapi BM25 only
    - ``tfidf`` — char n-gram TF-IDF only
    - ``bm25_fallback`` (default) — BM25, then TF-IDF when BM25 finds nothing
    """
    mode = normalize_ranker_name(name)
    if mode == "bm25":
        return Bm25Ranker()
    if mode == "tfidf":
        return TfidfRanker()
    return Bm25FallbackRanker()
