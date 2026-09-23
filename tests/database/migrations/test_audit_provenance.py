"""Migration preserves historical payloads and leaves unknown provenance NULL."""
from alembic import command
from sqlalchemy import create_engine, text, inspect


def test_upgrade_preserves_existing_audit_and_no_invented_provenance(alembic_config, temp_sqlite_url):
    command.upgrade(alembic_config, "34f4e80340ee")
    engine = create_engine(temp_sqlite_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("""INSERT INTO audit_logs
          (id,actor,action,affected_entity_type,affected_entity_id,old_value,new_value,reason,approval_status,occurred_at)
          VALUES ('00000000000040008000000000000001','synthetic','add_transaction','transaction',NULL,NULL,
          '{"synthetic":true}','synthetic','EXPLICITLY_APPROVED','2026-01-02 00:00:00')""")
        before = connection.exec_driver_sql("SELECT * FROM audit_logs").mappings().one()
        before = dict(before)
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        after = dict(connection.exec_driver_sql("SELECT * FROM audit_logs").mappings().one())
        assert {key: after[key] for key in before} == before
        assert all(after[key] is None for key in ("model_or_agent", "tool", "source"))
    command.downgrade(alembic_config, "34f4e80340ee")
    with engine.connect() as connection:
        assert dict(connection.exec_driver_sql("SELECT * FROM audit_logs").mappings().one()) == before
    command.upgrade(alembic_config, "head")
    assert {"model_or_agent", "tool", "source"} <= {c["name"] for c in inspect(engine).get_columns("audit_logs")}
    engine.dispose()
