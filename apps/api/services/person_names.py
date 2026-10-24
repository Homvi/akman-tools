"""Order-/case-/accent-insensitive person name identity."""

from __future__ import annotations

import unicodedata


def _fold_token(token: str) -> str:
    """Lowercase + strip diacritics from one name token."""
    decomposed = unicodedata.normalize("NFD", token.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def name_identity_key(name: str) -> str:
    """Same multiset of name tokens → same key, regardless of order/case/accents.

    Example: ``Brewka Patryk Daniel`` and ``Patryk Daniel Brewka`` both map to
    ``brewka daniel patryk``. Different token counts stay distinct.
    """
    tokens = [_fold_token(t) for t in str(name or "").split() if t]
    tokens = [t for t in tokens if t]
    if not tokens:
        return ""
    return " ".join(sorted(tokens))


def person_key(name: str) -> str:
    """Stable DB / lookup key for a person name (alias of ``name_identity_key``)."""
    return name_identity_key(name)
