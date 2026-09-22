"""
Entity ID helpers for Personal OS v0.1.

Source of truth: ADR-007 (Identifier Strategy) — every entity primary
key is UUID v4. This module is a thin wrapper around the standard
library `uuid` module; it does not implement a custom ID framework,
a typed ID wrapper class, or per-entity ID types.
"""

from __future__ import annotations

import uuid


def new_id() -> uuid.UUID:
    """Generate a new UUID v4 entity identifier."""
    return uuid.uuid4()


def parse_id(value: str) -> uuid.UUID:
    """
    Parse a UUID from its canonical string form.

    Raises ValueError if `value` is not a well-formed UUID string.
    Does not enforce that the parsed UUID is version 4 — a stored ID
    that arrived from outside Personal OS (e.g. a future import) may
    be a valid UUID of a different version; only IDs *generated* by
    Personal OS via new_id() are guaranteed to be v4.
    """
    return uuid.UUID(value)
