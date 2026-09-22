"""Step 6 -- AuditLog append/read."""

from __future__ import annotations

from personal_os.domain.datetime import utc_now
from personal_os.domain.ids import new_id
from personal_os.domain.records import AuditLogRecord
from personal_os.repository.audit_logs import AuditLogRepository


def test_audit_log_append_and_read(session_factory):
    session = session_factory()
    try:
        repo = AuditLogRepository(session)
        record = AuditLogRecord(
            id=new_id(),
            actor="test-suite",
            action="synthetic_test_write",
            affected_entity_type="Account",
            approval_status="NOT_APPLICABLE",
            occurred_at=utc_now(),
            reason="Step 6 repository test -- synthetic data only",
        )

        repo.add(record)
        session.commit()

        listed = repo.list_all()
        assert listed == [record]
    finally:
        session.close()
