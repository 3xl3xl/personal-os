"""Migration adds external_transaction_links with the ADR-014 dedup identity
UNIQUE constraint, and downgrade removes it cleanly."""
from alembic import command
from sqlalchemy import create_engine, inspect


def test_upgrade_creates_table_with_dedup_unique_constraint_and_downgrade_removes_it(
    alembic_config, temp_sqlite_url
):
    command.upgrade(alembic_config, "audit_provenance_v1")
    engine = create_engine(temp_sqlite_url)
    assert "external_transaction_links" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(alembic_config, "head")
    engine = create_engine(temp_sqlite_url)
    inspector = inspect(engine)
    assert "external_transaction_links" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("external_transaction_links")}
    assert columns == {
        "id", "source", "external_office_id", "external_account_id",
        "external_transaction_id", "transaction_id", "imported_at",
    }
    unique_constraints = inspector.get_unique_constraints("external_transaction_links")
    identity_columns = {
        "source", "external_office_id", "external_account_id", "external_transaction_id",
    }
    assert any(set(uc["column_names"]) == identity_columns for uc in unique_constraints)
    fks = inspector.get_foreign_keys("external_transaction_links")
    assert any(fk["referred_table"] == "transactions" for fk in fks)
    engine.dispose()

    command.downgrade(alembic_config, "audit_provenance_v1")
    engine = create_engine(temp_sqlite_url)
    assert "external_transaction_links" not in inspect(engine).get_table_names()
    engine.dispose()

    command.upgrade(alembic_config, "head")
    engine = create_engine(temp_sqlite_url)
    assert "external_transaction_links" in inspect(engine).get_table_names()
    engine.dispose()


def test_dedup_unique_constraint_is_enforced_at_the_database_level(
    alembic_config, temp_sqlite_url
):
    command.upgrade(alembic_config, "head")
    engine = create_engine(temp_sqlite_url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO accounts (id, name, account_type, currency_code, opened_at, status) "
            "VALUES ('00000000000040008000000000000001','synthetic','CASH','JPY','2026-01-01 00:00:00','ACTIVE')"
        )
        connection.exec_driver_sql(
            "INSERT INTO transactions (id, account_id, transaction_type, amount_minor, currency_code, occurred_at, status) "
            "VALUES ('00000000000040008000000000000002','00000000000040008000000000000001','NORMAL',1000,'JPY','2026-01-01 00:00:00','ACTIVE')"
        )
        connection.exec_driver_sql(
            "INSERT INTO external_transaction_links "
            "(id, source, external_office_id, external_account_id, external_transaction_id, transaction_id, imported_at) "
            "VALUES ('00000000000040008000000000000003','FREEE','office-1','wallet-1','line-1',"
            "'00000000000040008000000000000002','2026-01-01 00:00:00')"
        )
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO external_transaction_links "
                "(id, source, external_office_id, external_account_id, external_transaction_id, transaction_id, imported_at) "
                "VALUES ('00000000000040008000000000000004','FREEE','office-1','wallet-1','line-1',"
                "'00000000000040008000000000000002','2026-01-01 00:00:00')"
            )
    engine.dispose()
