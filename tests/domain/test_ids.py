"""Tests for personal_os.domain.ids — see ADR-007."""

from __future__ import annotations

import uuid

from personal_os.domain.ids import new_id, parse_id


def test_generated_id_is_uuid() -> None:
    assert isinstance(new_id(), uuid.UUID)


def test_generated_id_is_version_4() -> None:
    assert new_id().version == 4


def test_uniqueness_sanity() -> None:
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_parse_id_roundtrip() -> None:
    generated = new_id()
    parsed = parse_id(str(generated))
    assert parsed == generated
    assert parsed.version == 4
